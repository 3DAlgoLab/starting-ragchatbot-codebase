from typing import List, Tuple, Optional, Dict
import os
from document_processor import DocumentProcessor
from vector_store import VectorStore
from ai_generator import AIGenerator
from session_manager import SessionManager
from search_tools import ToolManager, CourseSearchTool
from models import Course

class RAGSystem:
    """Main orchestrator for the Retrieval-Augmented Generation system"""
    
    def __init__(self, config):
        self.config = config
        
        # Initialize core components
        self.document_processor = DocumentProcessor(config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        self.vector_store = VectorStore(config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS)
        self.ai_generator = AIGenerator(config.SGLANG_BASE_URL, config.SGLANG_MODEL)
        self.session_manager = SessionManager(config.MAX_HISTORY)
        
        # Initialize search tools
        self.tool_manager = ToolManager()
        self.search_tool = CourseSearchTool(self.vector_store)
        self.tool_manager.register_tool(self.search_tool)
    
    def add_course_document(self, file_path: str) -> Tuple[Course, int]:
        """
        Add a single course document to the knowledge base.
        
        Args:
            file_path: Path to the course document
            
        Returns:
            Tuple of (Course object, number of chunks created)
        """
        try:
            # Process the document
            course, course_chunks = self.document_processor.process_course_document(file_path)
            
            # Add course metadata to vector store for semantic search
            self.vector_store.add_course_metadata(course)
            
            # Add course content chunks to vector store
            self.vector_store.add_course_content(course_chunks)
            
            return course, len(course_chunks)
        except Exception as e:
            print(f"Error processing course document {file_path}: {e}")
            return None, 0
    
    def add_course_folder(self, folder_path: str, clear_existing: bool = False) -> Tuple[int, int]:
        """
        Add all course documents from a folder.
        
        Args:
            folder_path: Path to folder containing course documents
            clear_existing: Whether to clear existing data first
            
        Returns:
            Tuple of (total courses added, total chunks created)
        """
        total_courses = 0
        total_chunks = 0
        
        # Clear existing data if requested
        if clear_existing:
            print("Clearing existing data for fresh rebuild...")
            self.vector_store.clear_all_data()
        
        if not os.path.exists(folder_path):
            print(f"Folder {folder_path} does not exist")
            return 0, 0
        
        # Get existing course titles to avoid re-processing
        existing_course_titles = set(self.vector_store.get_existing_course_titles())
        
        # Process each file in the folder
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if os.path.isfile(file_path) and file_name.lower().endswith(('.pdf', '.docx', '.txt')):
                try:
                    # Check if this course might already exist
                    # We'll process the document to get the course ID, but only add if new
                    course, course_chunks = self.document_processor.process_course_document(file_path)
                    
                    if course and course.title not in existing_course_titles:
                        # This is a new course - add it to the vector store
                        self.vector_store.add_course_metadata(course)
                        self.vector_store.add_course_content(course_chunks)
                        total_courses += 1
                        total_chunks += len(course_chunks)
                        print(f"Added new course: {course.title} ({len(course_chunks)} chunks)")
                        existing_course_titles.add(course.title)
                    elif course:
                        print(f"Course already exists: {course.title} - skipping")
                except Exception as e:
                    print(f"Error processing {file_name}: {e}")
        
        return total_courses, total_chunks
    
    def query(self, query: str, session_id: Optional[str] = None) -> Tuple[str, List[str]]:
        """
        Process a user query using the RAG system with automatic search.

        Args:
            query: User's question
            session_id: Optional session ID for conversation context

        Returns:
            Tuple of (response, sources list)
        """
        # FALLBACK APPROACH: Since Phi-4 doesn't support tool calling reliably,
        # we always search first and provide context to the AI

        # Perform search automatically
        search_results = self.vector_store.search(query=query)

        # Extract sources from search results
        sources = []
        context_text = ""

        if not search_results.is_empty() and not search_results.error:
            # Build context from search results
            context_parts = []
            for doc, meta in zip(search_results.documents, search_results.metadata):
                course_title = meta.get('course_title', 'unknown')
                lesson_num = meta.get('lesson_number')

                # Build source information
                source_text = course_title
                if lesson_num is not None:
                    source_text += f" - Lesson {lesson_num}"

                # Get lesson link if available
                lesson_link = None
                if lesson_num is not None:
                    lesson_link = self.vector_store.get_lesson_link(course_title, lesson_num)

                # Store source with link
                source_obj = {"text": source_text}
                if lesson_link:
                    source_obj["link"] = lesson_link
                sources.append(source_obj)

                # Add to context
                context_parts.append(f"[{source_text}]\n{doc}")

            context_text = "\n\n".join(context_parts)


        # Get conversation history if session exists
        history = None
        if session_id:
            history = self.session_manager.get_conversation_history(session_id)

        # Create enhanced prompt with search context
        if context_text:
            prompt = f"""Use the following course content to answer the question. Provide a direct, concise answer without mentioning the sources or that you searched.

Course Content:
{context_text}

Question: {query}"""
        else:
            prompt = f"""Answer this question. If it's about course materials and no relevant content was found, say so briefly.

Question: {query}"""

        # Generate response using AI WITHOUT tools (since Phi-4 doesn't support them reliably)
        response = self.ai_generator.generate_response(
            query=prompt,
            conversation_history=history,
            tools=None,  # Disable tools
            tool_manager=None
        )

        # Update conversation history
        if session_id:
            self.session_manager.add_exchange(session_id, query, response)

        # Return response with sources from search
        return response, sources
    
    def get_course_analytics(self) -> Dict:
        """Get analytics about the course catalog"""
        return {
            "total_courses": self.vector_store.get_course_count(),
            "course_titles": self.vector_store.get_existing_course_titles()
        }