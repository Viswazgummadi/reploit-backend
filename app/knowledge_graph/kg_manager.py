# backend/app/knowledge_graph/kg_manager.py

from neo4j import GraphDatabase
from flask import current_app
from langchain.graphs import Neo4jGraph
from langchain.chains import GraphCypherQAChain
from langchain_google_genai import ChatGoogleGenerativeAI
# NEW: Import for building custom prompts
from langchain.prompts import PromptTemplate

# NEW: A more advanced prompt that tells the LLM how to use our specific dataSourceId
CYPHER_GENERATION_TEMPLATE = """
Task:
Generate a Cypher query to answer the user's question.
The user is asking about a specific software repository identified by the `dataSourceId`: "{data_source_id}".
ALL nodes in the graph are labeled with a `dataSourceId` property. Your query MUST use this property in a WHERE clause to filter for the correct repository.

Schema:
{schema}

Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.
If you cannot generate a query, return a blank string.

Examples:
# How many functions are in the file "main.py"?
MATCH (f:File {{path: "main.py", dataSourceId: "{data_source_id}"}})-[:DEFINES]->(func:Function)
RETURN count(func)

# What functions does "login_user" call?
MATCH (caller:Function {{name: "login_user", dataSourceId: "{data_source_id}"}})-[:CALLS]->(callee:Function)
RETURN callee.name

Question: {question}
Cypher Query:
"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question", "data_source_id"], template=CYPHER_GENERATION_TEMPLATE
)
class KnowledgeGraphManager:
    """Manages all interactions with the Neo4j Knowledge Graph."""
    def __init__(self):
        uri = current_app.config.get('NEO4J_URI')
        user = current_app.config.get('NEO4J_USERNAME')
        password = current_app.config.get('NEO4J_PASSWORD')

        if not all([uri, user, password]):
            raise ValueError("Neo4j credentials are not configured in the application.")
            
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self.graph = Neo4jGraph(url=uri, username=user, password=password)

    def close(self):
        """Closes the database connection driver."""
        if self._driver:
            self.close()

    def run_query(self, query, parameters=None):
        """A generic method to run a Cypher query against the database."""
        with self._driver.session() as session:
            result = session.run(query, parameters)
            return [record for record in result]
    def query_graph(self, natural_language_query: str, data_source_id: str) -> str:
        """
        Takes a natural language query AND a data_source_id, converts it to a
        Cypher query, executes it, and returns a natural language response.
        """
        current_app.logger.info(f"KG Tool: Received query -> '{natural_language_query}' for data source '{data_source_id}'")
        try:
            llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0, convert_system_message_to_human=True)

            # We now use our custom prompt that includes the data_source_id
            chain = GraphCypherQAChain.from_llm(
                graph=self.graph,
                llm=llm,
                cypher_prompt=CYPHER_GENERATION_PROMPT.partial(data_source_id=data_source_id), # Pass the ID to the prompt
                verbose=True
            )

            result = chain.invoke({"query": natural_language_query})
            
            answer = result.get("result", "I could not find an answer in the knowledge graph for that question.")
            current_app.logger.info(f"KG Tool: Produced answer -> '{answer}'")
            return answer
            
        except Exception as e:
            current_app.logger.error(f"Error querying knowledge graph: {e}", exc_info=True)
            return "There was an error while querying the knowledge graph."
        
    def add_file_node(self, data_source_id: str, file_path: str):
        """Adds a 'File' node to the graph if it doesn't already exist."""
        query = (
            "MERGE (f:File {path: $file_path, dataSourceId: $data_source_id}) "
            "RETURN f"
        )
        parameters = {"file_path": file_path, "data_source_id": data_source_id}
        self.run_query(query, parameters)
        current_app.logger.debug(f"KG: Merged File node for {file_path}")

    def add_function_node(self, data_source_id: str, file_path: str, function_name: str):
        """Adds a 'Function' node and links it to its containing 'File' node."""
        query = (
            "MERGE (file:File {path: $file_path, dataSourceId: $data_source_id}) "
            "MERGE (func:Function {name: $function_name, file_path: $file_path, dataSourceId: $data_source_id}) "
            "MERGE (file)-[:DEFINES]->(func)"
        )
        parameters = {
            "file_path": file_path,
            "function_name": function_name,
            "data_source_id": data_source_id
        }
        self.run_query(query, parameters)
        current_app.logger.debug(f"KG: Merged Function '{function_name}' and DEFINES relationship.")

    def clear_data_source_data(self, data_source_id: str):
        """Deletes all nodes and their relationships associated with a specific data source."""
        query = (
            "MATCH (n {dataSourceId: $data_source_id}) "
            "DETACH DELETE n"
        )
        parameters = {"data_source_id": data_source_id}
        self.run_query(query, parameters)
        current_app.logger.info(f"KG: Cleared all graph data for data source {data_source_id}.")