#%pip install -q langchain-core langchain-community crewai[tools] langchain-groq

#https://supabase.com/dashboard/project/iyhhhfugyygydzyhelbj?showConnect=true

import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Tuple, Union

import pandas as pd
from crewai import Agent, Crew, Process, Task
from crewai.tools import tool
from langchain.schema import AgentFinish
from langchain.schema.output import LLMResult
from langchain_community.tools.sql_database.tool import (
    InfoSQLDatabaseTool,
    ListSQLDatabaseTool,
    QuerySQLCheckerTool,
    QuerySQLDataBaseTool,
)
from langchain_community.utilities.sql_database import SQLDatabase
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

import requests
import asyncio
import telegram

import os
from dotenv import load_dotenv


# TOKEN = "8116010104:AAGKeSQx7PGYUWoZ3T5_JWB7w5eq3hA-sZk"
# chat_id = '1961419857'

load_dotenv()
# os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
os.environ["CREWAI_TELEMETRY_DISABLED"] = "1"

# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# SUPABASE_API_KEY= os.getenv("SUPABASE_API_KEY")
# TELEGRAM_TESTUSER_ID= os.getenv("TELEGRAM_TESTUSER_ID")
# TELEGRAM_TESTUSER_ID= 1961419857

#for Streamlit cloud 
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
SUPABASE_API_KEY= st.secrets["SUPABASE_API_KEY"]
TELEGRAM_TESTUSER_ID= st.secrets["TELEGRAM_TESTUSER_ID"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]



# Step 3. Load Data and Save to SQLite Database
# Load your dataset into a DataFrame and save it to an SQLite database:

# Load the dataset
# df = pd.read_csv("ds_salaries.csv")
# df.head()

# Save the dataframe to an SQLite database
# connection = sqlite3.connect("../database/salaries.db")
# df.to_sql(name="salaries", con=connection)

# Step 4. Set Up Logging
# Configure a logger to track LLM prompts and responses:

import re

def escape_markdown(text):
    # Escape Telegram Markdown special characters
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

@dataclass
class Event:
    event: str
    timestamp: str
    text: str

def _current_time() -> str:
    return datetime.now(timezone.utc).isoformat()

class LLMCallbackHandler(BaseCallbackHandler):
    def __init__(self, log_path: Path):
        self.log_path = log_path

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> Any:
        event = Event(event="llm_start", timestamp=_current_time(), text=prompts[0])
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(event)) + "\n")

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any:
        generation = response.generations[-1][-1].message.content
        event = Event(event="llm_end", timestamp=_current_time(), text=generation)
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(asdict(event)) + "\n")

# Step 5. Initialize the Language Model
# Set up the language model (LLM) with the logging callback:

# Replace this:
# llm = ChatGroq(api_key="YOUR_GROQ_API_KEY", ...)

# With this:
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    api_key= OPENAI_API_KEY ,  # Or use environment variable
    model="gpt-4o",          # Or another OpenAI model
    temperature=0.2
)
       

# Step 6. Create SQL Tools
# Define the SQL tools using the @tool decorator:

# Establish a database connection
# db = SQLDatabase.from_uri("sqlite:///salaries.db")
# db = SQLDatabase.from_uri("sqlite:///poultry_health.db")
# db = SQLDatabase.from_uri("postgresql://postgres:OneSummerDay@db.iyhhhfugyygydzyhelbj.supabase.co:5432/postgres")
db = SQLDatabase.from_uri(SUPABASE_API_KEY)
# Tool 1: List all the tables in the database
@tool("list tables")
def list_tables() -> str:
    """List all tables in the database."""
    return ListSQLDatabaseTool(db=db).invoke("")

# Tool 2: Return the schema and sample rows for given tables
@tool("tables_schema")
def tables_schema(tables: str) -> str:
    """Return the schema and sample rows for given tables."""
    tool = InfoSQLDatabaseTool(db=db)
    return tool.invoke(tables)

# Tool 3: Executes a given SQL query
@tool("execute_sql")
def execute_sql(sql_query: str) -> str:
    """Execute a given SQL query and return the result."""
    return QuerySQLDataBaseTool(db=db).invoke(sql_query)

# Tool 4: Checks the SQL query before executing it
@tool("check_sql")
def check_sql(sql_query: str) -> str:
    """Check the SQL query for correctness before executing."""
    return QuerySQLCheckerTool(db=db, llm=llm).invoke({"query": sql_query})

result= check_sql.run("SELECT * WHERE salary > 10000 LIMIT 5 table = salaries")
print(result)

# TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Set in your .env
# TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")      # Set in your .env

@tool("send_telegram_alert")
def send_telegram_alert(message: str):
    """Send an alert message to a Telegram chat."""
    # if chat_id is None:
    #     chat_id = TELEGRAM_CHAT_ID
    
    print("Alert sent to Telegram---------->")
    bot_token = TELEGRAM_TOKEN
    chat_id = TELEGRAM_TESTUSER_ID
    # message_text = "Hello from your Telegram bot!"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        # "parse_mode": "MarkdownV2"
    }
    response = requests.post(url, data=payload)
    print(response.json())
   
    # bot = telegram.Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    # async with bot:
    #     await bot.send_message(text=message, chat_id=chat_id)


    print(message)
    return message
# def send_telegram_alert(message: str, chat_id: str = None):
#     """Send an alert message to a Telegram chat."""
#     # if chat_id is None:
#     #     chat_id = TELEGRAM_CHAT_ID
#     # url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
#     # payload = {
#     #     "chat_id": chat_id,
#     #     "text": message,
#     #     "parse_mode": "Markdown"
#     # }
#     # response = requests.post(url, data=payload)
#     print("Alert sent to Telegram---------->")
#     print(message)
#     return response.ok

# Step 7. Create Agents
# Define the agents for different roles:

# Agent 1: Database Developer Agent
sql_dev = Agent(
    role="Senior Database Developer",
    goal="Construct and execute SQL queries based on a request",
    backstory=dedent(
        """
        You are an experienced database engineer who is master at creating efficient and complex SQL queries.
        Use the `list_tables` to find available tables.
        Use the `tables_schema` to understand the metadata for the tables.
        Use the `execute_sql` to execute queries.
        Use the `check_sql` to validate your queries.
        """
    ),
    llm=llm,
    tools=[list_tables, tables_schema, execute_sql, check_sql],
    allow_delegation=False,
)

# Agent 2: Data Analyst Agent
data_analyst = Agent(
    role="Senior Data Analyst",
    goal="Analyze the database data response and write a detailed response",
    backstory=dedent(
        """
        You have deep experience with analyzing datasets using Python.
        Your work is always based on the provided data and is clear,
        easy-to-understand and to the point. You have attention
        to detail and always produce very detailed work.
        """
    ),
    llm=llm,
    allow_delegation=False,
)

# Agent 3: Report Editor Agent
report_writer = Agent(
    role="Senior Report Editor",
    goal="Write an executive summary based on the analysis",
    backstory=dedent(
        """
        Your writing is known for clear and effective communication.
        Summarize long texts into concise bullet points with key details.
        """
    ),
    llm=llm,
    allow_delegation=False,
)


# Agent 4: Data Insert Validation Agent
data_insert_validator = Agent(
    role="Data Insert Validation Agent",
    goal="Validate that all required data for SQL insert is provided",
    backstory=dedent(
        """
        You are responsible for ensuring data integrity before any SQL insert operation.
        Your job is to check that all required fields from the user form are present and not missing.
        If any required field is missing, you must report which one and why.
        """
    ),
    llm=llm,
    allow_delegation=False,
)

# Agent 4: Data Json Validation Agent
data_json_validator = Agent(
    role="Data Json Validation Agent",
    goal="Validate that all mandatory data/fields in the provided json for SQL insert is provided",
    backstory=dedent(
        """
        You good in understanding JSON structure and extracting data from JSON.
        You are responsible for ensuring data integrity before any SQL insert operation.
        Your job is to check that all mandatory fields from the user form stored in json are present and not missing.
        You can check the JSON structure and validate value are not empty in all mandatory fields.
        All mandatory fields' value should not be empty.
        If any mandatory field is missing, you must report which one and why.
        """
    ),
    llm=llm,
    allow_delegation=False,
)


# Step 8. Create Tasks
# Define the tasks for the agents:

# Task 1: Extract data required for the user query
extract_data = Task(
    description="Extract data that is required for the query {query}.",
    agent=sql_dev,
    expected_output=(
        "For SELECT queries: Return a list of JSON objects, where each object represents a record with field names as keys and their corresponding values.\n"
        "For other SQL queries (INSERT, UPDATE, DELETE, etc.): Return a JSON object with a 'message' field indicating the result (e.g., success, error, or affected rows)."
    ),
)

# Task 2: Analyze the data from the database
analyze_data = Task(
    description="Analyze the data from the database and write an analysis for {query}.",
    expected_output="Detailed analysis text",
    agent=data_analyst,
    context=[extract_data],
)

# Task 3: Write an executive summary of the analysis
write_report = Task(
    description=dedent(
        """
        Write an executive summary of the report from the analysis. The report
        must be less than 100 words.
        """
    ),
    expected_output="Markdown report",
    agent=report_writer,
    context=[analyze_data],
)

# Task: Validate Insert Data
validate_insert_data = Task(
    description=dedent(
        """
        Check that all required data from the user form {query} for SQL insert is provided and no data is missing.
        If any required field's VALUE is missing, report which one and why.
        The objective is to ensure data completeness before insertion.
        """
    ),
    expected_output="Validation pass or fail with reason",
    agent=data_insert_validator,
    # context=[extract_data],  # Optionally, you can pass the extract_data task as context if needed
)

# Task: Validate Json Data
validate_json_data = Task(
    description=dedent(
        """
        Check that all mandatory key from the user form stored as JSON {query} for SQL insert is provided and no data is missing.
        If any mandatory field's VALUE is missing, report which one and why.
        The objective is to ensure all mandatory data are complete before insertion.
        If any mandatory field is missing, you must report was fail with reason. 
        And all mandatory fields' value are present you must report as pass.
        """
    ),
    expected_output="Validation result pass or fail with reason",
    agent=data_json_validator,
    # context=[extract_data],  # Optionally, you can pass the extract_data task as context if needed
)

# Task : Get data required from Json form to INSERT database
store_data = Task(

    description=dedent(
        """
        Extract Json data relate to the table for the query {query}.
        Check that all mandatory field are filled with data , set the complete_status field with True.
        Check if any mandatory field's VALUE is missing, set the complete_status field with False.
        Irregardless of complete_status's value, insert the record with the Json data from the user form.
        """
    ),
    agent=sql_dev,
    expected_output=(
        "For SELECT queries: Return a list of JSON objects, where each object represents a record with field names as keys and their corresponding values.\n"
        "For other SQL queries (INSERT, UPDATE, DELETE, etc.): Return a JSON object with a 'message' field indicating the result (e.g., success, error, or affected rows)."
    ),
)

# Task : Get data required from Json form to UDPATE database
update_data = Task(

    description=dedent(
        """
        Extract Json data relate to the table for the query {query}.
        Check that all mandatory field are filled with data , set the complete_status field with True.
        Check if any mandatory field's VALUE is missing, set the complete_status field with False.
        Irregardless of complete_status's value, Update the record based on given value in case_id.
        """
    ),
    agent=sql_dev,
    expected_output=(
        "For SELECT queries: Return a list of JSON objects, where each object represents a record with field names as keys and their corresponding values.\n"
        "For other SQL queries (INSERT, UPDATE, DELETE, etc.): Return a JSON object with a 'message' field indicating the result (e.g., success, error, or affected rows)."
    ),
)

# Step 9. Setup The Crew
# Initialize the Crew with agents and tasks:

# crew = Crew(
#     agents=[sql_dev, data_analyst, report_writer],
#     tasks=[extract_data, analyze_data, write_report],
#     process=Process.sequential,
#     verbose=True,
#     memory=False,
#     output_log_file="crew.log",
# )
crew = Crew(
    agents=[sql_dev],
    tasks=[extract_data],
    process=Process.sequential,
    verbose=True,
    memory=False,
    output_log_file="crew.log",
)



# Step 10. Kickoff the Crew
# Run the Crew with different queries:

# inputs = {
#     "query": "Effects on salary (in USD) based on company location, size and employee experience"
# }
# result = crew.kickoff(inputs=inputs)
# print(result)
# print(">>>>>>>>>>>>>>>>>>>>>>>")

# inputs = {
#     "query": "How is the `Machine Learning Engineer` salary in USD affected by remote positions"
# }
# result = crew.kickoff(inputs=inputs)
# print("result.......................")
# print(result)


# print(">>>>>>>>>>>>>>>>>>>>>>>")
# inputs = {
#     "query": "How is the salary in USD based on employment type and experience level? "
# }
# result = crew.kickoff(inputs=inputs)
# print(result)

# inputs = {
#     "query": "How are Bio Security violations?"
# }
# result = crew.kickoff(inputs=inputs)
# print("result.......................")
# print(result)

# inputs = {
#     "query": "Insert into Bio Security record with Location = 'ttt777',violation= 'No yellow boot' and image_analysis = `Test image`"
# }
# result = crew.kickoff(inputs=inputs)
# print("result.......................")
# print(result)



# inputs = {
#     "query": "Give the poultry heath records where the symptom is `Cough`"
# }
# result = crew.kickoff(inputs=inputs)
# print("result.......................")
# print(result)


print("END------------------")





# Agent 5: Alert Agent
alert_agent = Agent(
    role="Alert Agent",
    goal="Send an alert or notification based on validation results",
    backstory=dedent(
        """
        You are responsible for sending alerts or notifications when validation is completed.
        You receive the validation result, get the message in the result and notify the relevant parties.
        """
    ),
    llm=llm,
    tools=[send_telegram_alert],
    allow_delegation=False,
)

# Task: Alert Task
alert_task = Task(
    description="Send an alert or notification based on the validation result.",
    agent=alert_agent,
    expected_output="Alert sent or notification logged based on validation outcome.",
    context=[validate_insert_data],
)

alert_json_task = Task(
    description=dedent(
        """
        Send an alert or notification based on the validation result..
        Ensure all alert message is provided with case_id. 
        If the validation result is fail, the alert message must include the reason.

        """
    ),
    agent=alert_agent,
    expected_output="Alert sent or notification logged based on validation outcome.",
    context=[validate_json_data],
)

# Example Task for Alert Agent
def format_alert_message(validation_info: dict) -> str:
    # Example: validation_info = {"email": "...", "error": "..."}
    email = validation_info.get("email", "unknown")
    error = validation_info.get("error", "Validation failed.")
    return f"⚠️ *Validation Failed*\nUser: `{email}`\nReason: {error}"

# Example usage in your workflow (pseudo-code, adapt as needed):
def handle_failed_validation(validation_info):
    message = format_alert_message(validation_info)
    # Optionally map email to Telegram chat_id if needed
    send_telegram_alert(message)

