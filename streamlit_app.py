__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import streamlit as st
import sqlite3
from datetime import datetime
from myagent import sql_dev, extract_data, Crew, Process, data_analyst, \
    analyze_data, data_insert_validator, validate_insert_data, alert_agent,alert_task, \
    data_json_validator,validate_json_data,store_data,alert_json_task,update_data
from openai import OpenAI
import openai
import base64
import json
import psycopg2
from dotenv import load_dotenv
import os
import random
import string
import time



import sys
sys.path.append('./')

# Load environment variables from .env
load_dotenv()

# Fetch variables
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")

def generate_custom_id():
    timestamp = str(int(time.time()))
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ID-{timestamp}-{random_chars}"

#for update incident report case ID select box 
def handle_change_selectcaseid():
    st.session_state.selected_value = st.session_state.case_id_select


def fetch_case_ids_by_status(status, case_owner):
    try:
        conn = psycopg2.connect(
                        user=USER,
                        password=PASSWORD,
                        host=HOST,
                        port=PORT,
                        dbname=DBNAME
                    )

        print("Connection successful!")
    
        cursor = conn.cursor()

        query = "SELECT case_id FROM poultry_health_records WHERE case_status = %s AND case_owner = %s"
        print(f"[DEBUG] Query: {query}")


        cursor.execute(query, (status, case_owner))
        case_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        print("Connection closed.")
        return case_ids
    except Exception as e:
        cursor.close()
        conn.close()
        print("Connection closed.")
        st.error(f"Error fetching case IDs: {e}")
        return []

def on_status_change():
    case_owner = st.session_state.case_owner
    status = st.session_state.case_status
    st.session_state.case_id_list = fetch_case_ids_by_status(status, case_owner)
    # Reset selected case when status changes
    st.session_state.selected_case = None
    print(f"[DEBUG] Status changed to {status}")
    print(f"[DEBUG] Updated case_id_list: {st.session_state.case_id_list}")
    print(f"[DEBUG] Updated case_id_list: {st.session_state.case_owner}")

def on_case_select():
    print(f"[DEBUG] Selected case: {st.session_state.selected_case}")
#--------------------------------------------------------

client = OpenAI()  # Uses OPENAI_API_KEY from environment

if 'case_id_list' not in st.session_state:
    st.session_state.case_id_list = []
if 'selected_case' not in st.session_state:
    st.session_state.selected_case = None
if 'case_status' not in st.session_state:
    st.session_state.case_status = "Open" 

# Main app
st.title("Poultry Farm Management System")

# Sidebar navigation
# Sidebar role selection
role = st.sidebar.selectbox("Select Role", ["Farmer", "Sale", "Technical"])

# Role-based menu options
def get_menu_options(role):
    if role == "Farmer":
        return ["New Incident Report", "Update Incident Report", "Submit Incident Report"]
    elif role == "Sale":
        return ["Biosecurity Entry", "Sale Management", "Incident Report Query"]
    elif role == "Technical":
        return ["Biosecurity Entry", "Technical Management", "Incident Report Query"]
    else:
        return []

menu_options = get_menu_options(role)
menu = st.sidebar.selectbox("Menu", menu_options)


if menu == "New Incident Report":
    st.header("Create New Poultry Incident Data Entry")
    gen_case_id = generate_custom_id()
    with st.form("New Incident Report"):
        case_id = st.text_input("Case ID", value=gen_case_id, disabled=True)
        body_weight = st.number_input("Body Weight (kg)", min_value=0.0)
        body_temp = st.number_input("Body Temperature (°C)", min_value=0.0)
        vaccines = st.text_input("Vaccination Records")
        symptoms = st.text_input("Symptoms")
        uploaded_image = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])
        image_analysis = ""
        submitted = st.form_submit_button("Submit")
        if submitted:
            if uploaded_image is not None:
                st.image(uploaded_image, caption="Uploaded Image", use_column_width=True)
                image_bytes = uploaded_image.read()
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                prompt = "Describe what you see in this poultry health image."
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an expert poultry farm assistant. Describe the content of the uploaded image for health analysis."},
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                        ]}
                    ],
                    max_tokens=256
                )
                image_analysis = response.choices[0].message.content
                st.info(f"Image Analysis: {image_analysis}")
            else:
                image_analysis = "No Photo"



            # Collect data into JSON format
            record_json = {
                "case_id": {"value": case_id, "requirement": "mandatory"},
                "body_weight": {"value": body_weight, "requirement": "mandatory"},
                "body_temperature": {"value": body_temp, "requirement": "mandatory"},
                "vaccination_records": {"value": vaccines, "requirement": "mandatory"},
                "symptoms": {"value": symptoms, "requirement": "optional"},
                "image_analysis": {"value": image_analysis, "requirement": "optional"},
                "created_at": {"value": str(datetime.now()), "requirement": "mandatory"},
                "SQL_type": {"value": "Insert", "requirement": "mandatory"},
                "Database_table": {"value": "poultry_health_records", "requirement": "mandatory"}
            }
            
            # Validation example
            missing_fields = [k for k, v in record_json.items() if v["requirement"] == "mandatory" and not v["value"]]
            if missing_fields:
                st.error(f"Missing mandatory fields: {', '.join(missing_fields)}")
            else:
                st.success("All mandatory fields are present.")
                st.json(record_json)
            st.write("Collected JSON:")
            st.json(record_json)

            # query_prompt = f"""
            # INSERT INTO poultry_health_records 
            # (body_weight, body_temperature, vaccination_records, symptoms, image_analysis, created_at)
            # VALUES 
            # ({body_weight}, {body_temp}, '{vaccines}', '{symptoms}', '{image_analysis}', '{datetime.now()}');
            # """

            crew_input = {"prompt": json.dumps(record_json)}

            crew = Crew(
                # agents=[data_json_validator,alert_agent,sql_dev],
                # tasks=[validate_json_data,alert_task,store_data],
                agents=[data_json_validator,alert_agent, sql_dev],
                tasks=[validate_json_data,alert_json_task, store_data],
                process=Process.sequential,
                verbose=True,
                memory=False,
                output_log_file="crew.log",
            )
            inputs = {"query": crew_input}
            result = crew.kickoff(inputs=inputs)
            st.write("Query Result:")
            st.code(result)

elif menu == "Biosecurity Entry":
    st.header("Biosecurity Data Entry")
    with st.form("bio_form"):
        location = st.text_input("Location")
        violation = st.text_input("Violation")
        image_analysis = st.text_area("Image Analysis")
        submitted = st.form_submit_button("Submit")
        
        if submitted:
            query_prompt = f"""
            INSERT INTO biosecurity_records 
            (location, violation, image_analysis, created_at)
            VALUES 
            ('{location}', '{violation}', '{image_analysis}', '{datetime.now()}');
            """
            
            crew = Crew(
                agents=[sql_dev],
                tasks=[extract_data],
                process=Process.sequential,
                verbose=True,
                memory=False,
                output_log_file="crew.log",
            )
            
            inputs = {"query": query_prompt}
            result = crew.kickoff(inputs=inputs)
            
            st.success("Record processed successfully!")
            st.write("Query Result:")
            try:
                # Try to parse result as JSON
                if isinstance(result, str):
                    parsed_result = json.loads(result)
                else:
                    parsed_result = result
                st.code(json.dumps(parsed_result, indent=2))
            except Exception:
                # Fallback: just display the raw result
                st.code(result)
            st.success("Record added successfully!")
            st.write(f"Added record: Location={location}, Violation={violation}")

elif menu == "Incident Report Query":
    st.header("Incident Report Query")
    query = st.text_area("Enter your query (SQL or natural language)")
    
    if st.button("Execute Query"):
        # Initialize Crew with the query
        crew = Crew(
            agents=[sql_dev, data_analyst],
            tasks=[extract_data, analyze_data],
            process=Process.sequential,
            verbose=True,
            memory=False,
            output_log_file="crew.log",
        )
        
        # Execute the query through CrewAI
        inputs = {"query": query}
        result = crew.kickoff(inputs=inputs)
        
        st.write("Query Results:")
        st.code(result)
        st.success("Query executed successfully!")

elif menu == "Update Incident Report":
    st.header("Update Poultry Incident Report")
    # Initialize session state for record_found and form fields
    if "record_found" not in st.session_state:
        st.session_state.record_found = False
    if "update_fields" not in st.session_state:
        st.session_state.update_fields = {}

    with st.form("health_update_form"):
        # Connect to the database
        connection = psycopg2.connect(
                        user=USER,
                        password=PASSWORD,
                        host=HOST,
                        port=PORT,
                        dbname=DBNAME
                    )

        print("Connection successful!")
        # Create a cursor to execute SQL queries
        cursor = connection.cursor()
        cursor.execute("SELECT case_id FROM poultry_health_records WHERE case_status IS NULL ")
        case_id_rows = cursor.fetchall()
        # Close the cursor and connection
        cursor.close()
        connection.close()
        print("Connection closed.")

        #list all the case IDs from the database
        
        case_id_list = [row[0] for row in case_id_rows]

        if case_id_list:
            case_record_id = st.selectbox("Select Record ID to Update", options=case_id_list, key="case_id_select")
            # st.write(f"Your selected case ID : {case_record_id}")
        else:
            st.warning("No records found in poultry_health_records.")

       
        fetch_btn = st.form_submit_button("Fetch Record")

        if fetch_btn:
            # Fetch the record from the database based on the selected case ID     
            #Supabase codes
            connection = psycopg2.connect(
                        user=USER,
                        password=PASSWORD,
                        host=HOST,
                        port=PORT,
                        dbname=DBNAME
                    )

            print("Connection successful!")
            # Create a cursor to execute SQL queries
            cursor = connection.cursor()
    
            cursor.execute(
                "SELECT body_weight, body_temperature, vaccination_records, symptoms, image_analysis FROM poultry_health_records WHERE case_id = %s",
                (case_record_id,))
            row = cursor.fetchone()
            # Close the cursor and connection
            cursor.close()
            connection.close()
            print("Connection closed.")
            if row:
                st.session_state.record_found = True
                st.session_state.update_fields = {
                    "body_weight": row[0],
                    "body_temp": row[1],
                    "vaccines": row[2],
                    "symptoms": row[3],
                    "image_analysis": row[4]
                }
                st.success("Record found. You can now update the fields below.")          
            else:
                st.session_state.record_found = False
                st.session_state.update_fields = {}
                st.error("Record not found. Please check the ID.")

        # Only display the update form if a record was found
        if st.session_state.record_found:
            update_fields = st.session_state.update_fields
            case_id = st.text_input("Case ID", value=case_record_id, disabled=True)
            new_body_weight = st.number_input("Body Weight (kg)", min_value=0.0, value=update_fields.get("body_weight", 0.0), key="update_weight")
            new_body_temp = st.number_input("Body Temperature (°C)", min_value=0.0, value=update_fields.get("body_temp", 0.0), key="update_temp")
            new_vaccines = st.text_input("Vaccination Records", value=update_fields.get("vaccines", ""), key="update_vaccines")
            new_symptoms = st.text_input("Symptoms", value=update_fields.get("symptoms", ""), key="update_symptoms")
            new_image_analysis = st.text_input("Image Analysis", value=update_fields.get("image_analysis", ""), key="update_image_analysis")
            uploaded_image = st.file_uploader("Upload New Image (optional)", type=["jpg", "jpeg", "png"], key="update_image")
            new_image_analysis = update_fields.get("image_analysis", "")

            #Submit button for update
            update_btn = st.form_submit_button("Update Record")
            if update_btn:
                #Call VLLM to get the new image analysis 
                if uploaded_image is not None:
                    st.image(uploaded_image, caption="Uploaded Image", use_column_width=True)
                    image_bytes = uploaded_image.read()
                    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                    prompt = "Describe what you see in this poultry health image."
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are an expert poultry farm assistant. Describe the content of the uploaded image for health analysis."},
                            {"role": "user", "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                            ]}
                        ],
                        max_tokens=256
                    )
                    new_image_analysis = response.choices[0].message.content
                    st.info(f"Image Analysis: {new_image_analysis}")
                # else: #don't update the image analysis if no new image is uploaded
                #     new_image_analysis = "No Photo"
                
                # Collect data into JSON format
                record_json = {
                    "case_id": {"value": case_id, "requirement": "mandatory"},
                    "body_weight": {"value": new_body_weight, "requirement": "mandatory"},
                    "body_temperature": {"value": new_body_temp, "requirement": "mandatory"},
                    "vaccination_records": {"value": new_vaccines, "requirement": "mandatory"},
                    "symptoms": {"value": new_symptoms, "requirement": "optional"},
                    "image_analysis": {"value": new_image_analysis, "requirement": "optional"},
                    "created_at": {"value": str(datetime.now()), "requirement": "mandatory"},
                    "SQL_type": {"value": "Update", "requirement": "mandatory"},
                    "Database_table": {"value": "poultry_health_records", "requirement": "mandatory"}
                }
                
                # Validation example
                missing_fields = [k for k, v in record_json.items() if v["requirement"] == "mandatory" and not v["value"]]
                if missing_fields:
                    st.error(f"Missing mandatory fields: {', '.join(missing_fields)}")
                else:
                    st.success("All mandatory fields are present.")
                    st.json(record_json)
                st.write("Collected JSON:")
                st.json(record_json)

                crew_input = {"prompt": json.dumps(record_json)}

                # Use Crew agent to construct and execute the UPDATE query
                # query_prompt = f"""
                # UPDATE poultry_health_records
                # SET body_weight={new_body_weight},
                #     body_temperature={new_body_temp},
                #     vaccination_records='{new_vaccines}',
                #     symptoms='{new_symptoms}',
                #     image_analysis='{new_image_analysis}'
                # WHERE case_id={case_record_id};
                # """

                crew = Crew(
                    # agents=[sql_dev, data_insert_validator],
                    # tasks=[extract_data, validate_insert_data],
                    agents=[data_json_validator,alert_agent, sql_dev],
                    tasks=[validate_json_data,alert_json_task, update_data],
                    process=Process.sequential,
                    verbose=True,
                    memory=False,
                    output_log_file="crew.log",
                )
                inputs = {"query": crew_input}
                result = crew.kickoff(inputs=inputs)
                st.success("Record updated successfully!")
                st.write("Query Result:")
                st.code(result)

elif menu == "Submit Incident Report":
    st.header("Submit Poultry Incident Report")
    # Initialize session state for record_found and form fields
    if "record_found" not in st.session_state:
        st.session_state.record_found = False
    if "update_fields" not in st.session_state:
        st.session_state.update_fields = {}
    with st.form("health_submit_form"):
        # Connect to the database
        connection = psycopg2.connect(
                        user=USER,
                        password=PASSWORD,
                        host=HOST,
                        port=PORT,
                        dbname=DBNAME
                    )

        print("Connection successful!")
        # Create a cursor to execute SQL queries
        cursor = connection.cursor()

        cursor.execute("SELECT case_id FROM poultry_health_records WHERE complete_status IS TRUE AND case_status IS NULL")
        case_id_rows = cursor.fetchall()
        # Close the cursor and connection
        cursor.close()
        connection.close()
        print("Connection closed.")

        #list all the case IDs from the database
        # case_id_list = [row[0] for row in case_id_rows]
        # if 'case_id_list' not in st.session_state:
        #     st.session_state.case_id_list = [row[0] for row in case_id_rows]
        #     print(f"[DEBUG] Initialized case_id_list: {st.session_state.case_id_list}")
        st.session_state.case_id_list = [row[0] for row in case_id_rows]
        print(f"[DEBUG] Initialized case_id_list: {st.session_state.case_id_list}")

        if st.session_state.case_id_list:
            case_record_id = st.selectbox("Select Record ID to Update", options=st.session_state.case_id_list, key="case_id_select")
            # st.write(f"Your selected case ID : {case_record_id}")
            fetch_btn = st.form_submit_button("Fetch Record")

            if fetch_btn:
                # Fetch the record from the database based on the selected case ID     
                #Supabase codes
                connection = psycopg2.connect(
                            user=USER,
                            password=PASSWORD,
                            host=HOST,
                            port=PORT,
                            dbname=DBNAME
                        )

                print("Connection successful!")
                # Create a cursor to execute SQL queries
                cursor = connection.cursor()
        
                cursor.execute(
                    "SELECT body_weight, body_temperature, vaccination_records, symptoms, image_analysis FROM poultry_health_records WHERE case_id = %s",
                    (case_record_id,))
                row = cursor.fetchone()
                # Close the cursor and connection
                cursor.close()
                connection.close()
                print("Connection closed.")
                if row:
                    st.session_state.record_found = True
                    st.session_state.update_fields = {
                        "body_weight": row[0],
                        "body_temp": row[1],
                        "vaccines": row[2],
                        "symptoms": row[3],
                        "image_analysis": row[4]
                    }
                    st.success("Record found. You can now check the fields below.")          
                else:
                    st.session_state.record_found = False
                    st.session_state.update_fields = {}
                    st.error("Record not found. Please check the ID.")

            # Only display the update form if a record was found
            if st.session_state.record_found:
                update_fields = st.session_state.update_fields
                case_id = st.text_input("Case ID", value=case_record_id, disabled=True)
                new_body_weight = st.number_input("Body Weight (kg)", min_value=0.0, value=update_fields.get("body_weight", 0.0), key="update_weight", disabled=True)
                new_body_temp = st.number_input("Body Temperature (°C)", min_value=0.0, value=update_fields.get("body_temp", 0.0), key="update_temp", disabled=True)
                new_vaccines = st.text_input("Vaccination Records", value=update_fields.get("vaccines", ""), key="update_vaccines", disabled=True)
                new_symptoms = st.text_input("Symptoms", value=update_fields.get("symptoms", ""), key="update_symptoms", disabled=True)
                new_image_analysis = st.text_input("Image Analysis", value=update_fields.get("image_analysis", ""), key="update_image_analysis", disabled=True)
                uploaded_image = st.file_uploader("Upload New Image (optional)", type=["jpg", "jpeg", "png"], key="update_image", disabled=True)
                new_image_analysis = update_fields.get("image_analysis", "")

                #Submit button for update
                confirm = st.checkbox("I confirm to submit and set this case as Open.")
                submit_btn = st.form_submit_button("Submit case")
                if submit_btn:
                    # Confirm with user before executing
                    if confirm:
                        try:
                            conn = psycopg2.connect(
                            user=USER,
                            password=PASSWORD,
                            host=HOST,
                            port=PORT,
                            dbname=DBNAME
                        )
                            cur = conn.cursor()
                            update_sql = "UPDATE poultry_health_records SET case_status = 'Open', case_owner = 'Sales' WHERE case_id = %s"
                            cur.execute(update_sql, (case_id,))
                            conn.commit()
                            st.success("Case status updated to Open.")
                            # Refresh the case_id_list after update
                            cur.execute("SELECT case_id FROM poultry_health_records WHERE case_status IS NULL OR case_status = ''")
                            case_id_rows = cur.fetchall()
                            # case_id_list = [row[0] for row in case_id_rows]
                            st.session_state.case_id_list = [row[0] for row in case_id_rows]
                            st.session_state.record_found = False  # Reset form state
                            st.info("Dropdown list updated. If you don't see changes, try reloading the page.")

                            continue_btn = st.form_submit_button("Continue")
                            if continue_btn:    
                                # Force a rerun to update the selectbox
                                st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")
                        finally:
                            if 'cur' in locals():
                                cur.close()
                            if 'conn' in locals():
                                conn.close()
                        st.success("Record updated successfully!")
                    else:
                        st.warning("Please confirm before submitting.")



        else:
            st.warning("No records found in poultry_health_records.")

       
        
                

elif menu == "Sale Management":
    st.header("Sale Management")
    if 'selected_case' not in st.session_state:
            st.session_state.selected_case = None
 # Initialize session state for record_found and form fields
    if "record_found" not in st.session_state:
        st.session_state.record_found = False
    if "update_fields" not in st.session_state:
        st.session_state.update_fields = {}
    if "case_owner" not in st.session_state:
        st.session_state.case_owner = None

    st.session_state.case_owner = "Sales"
    st.session_state.status = "Open"
    on_status_change()

    case_status = st.radio(
    "Select Case Status",
    options=["Open", "Close"],
    horizontal=True,
    key="case_status",
    on_change=on_status_change  # Added callback
    )

    # if case_status == "Open":
    #     case_id_list = fetch_case_ids_by_status(case_status)
    # elif case_status == "Close":
    #     case_id_list = fetch_case_ids_by_status(case_status)
    # else:
    #     case_id_list = []

    selected_case_id = st.selectbox("Select Case ID", options=st.session_state.case_id_list)
    st.session_state.selected_case = selected_case_id

    with st.form("sale_managemen_form"):
        

        fetch_btn = st.form_submit_button("Fetch Record")

        if fetch_btn:
            # Fetch the record from the database based on the selected case ID     
            #Supabase codes
            connection = psycopg2.connect(
                        user=USER,
                        password=PASSWORD,
                        host=HOST,
                        port=PORT,
                        dbname=DBNAME
                    )

            print("Connection successful!")
            # Create a cursor to execute SQL queries
            cursor = connection.cursor()

            cursor.execute(
                "SELECT body_weight, body_temperature, vaccination_records, symptoms, image_analysis,complete_status,case_status,case_owner,case_complete_reason FROM poultry_health_records WHERE case_id = %s",
                (selected_case_id,))
            row = cursor.fetchone()
            # Close the cursor and connection
            cursor.close()
            connection.close()
            print("Connection closed.")
            if row:
                st.session_state.record_found = True
                st.session_state.update_fields = {
                    "body_weight": row[0],
                    "body_temp": row[1],
                    "vaccines": row[2],
                    "symptoms": row[3],
                    "image_analysis": row[4],
                    "complete_status": row[5],
                    "case_status": row[6],
                    "case_owner": row[7],
                    "case_complete_reason": row[8]
                }
                st.success("Record found. You can now check the fields below.")          
            else:
                st.session_state.record_found = False
                st.session_state.update_fields = {}
                st.error("Record not found. Please check the ID.")
            
             # Only display the update form if a record was found
        if st.session_state.record_found:
            update_fields = st.session_state.update_fields
            case_id = st.text_input("Case ID", value=selected_case_id, disabled=True)
            new_body_weight = st.number_input("Body Weight (kg)", min_value=0.0, value=update_fields.get("body_weight", 0.0), key="update_weight", disabled=True)
            new_body_temp = st.number_input("Body Temperature (°C)", min_value=0.0, value=update_fields.get("body_temp", 0.0), key="update_temp", disabled=True)
            new_vaccines = st.text_input("Vaccination Records", value=update_fields.get("vaccines", ""), key="update_vaccines", disabled=True)
            new_symptoms = st.text_input("Symptoms", value=update_fields.get("symptoms", ""), key="update_symptoms", disabled=True)
            new_image_analysis = st.text_input("Image Analysis", value=update_fields.get("image_analysis", ""), key="update_image_analysis", disabled=True)
            uploaded_image = st.file_uploader("Upload New Image (optional)", type=["jpg", "jpeg", "png"], key="update_image", disabled=True)
            new_image_analysis = update_fields.get("image_analysis", "")
            complete_status = st.text_input("Complete Status", value=update_fields.get("complete_status", ""), key="update_complete_status", disabled=True)
            case_status = st.text_input("Case Status", value=update_fields.get("case_status", ""), key="update_case_status", disabled=True)
            case_owner = st.text_input("Case Owner", value=update_fields.get("case_owner", ""), key="update_case_owner", disabled=True)
            case_complete_reason = st.text_input("Case Complete Reason", value=update_fields.get("case_complete_reason", ""), key="update_case_complete_reason", disabled=False)

            if case_status == "Open":
                #Submit button for update
                confirm = st.checkbox("I confirm to submit and set this case as Close.")
                col1, col2 = st.columns(2)
                with col1:
                    submit_btn = st.form_submit_button("Submit case")
                with col2:
                    escalate_btn = st.form_submit_button("Escalate case")
                
                if submit_btn:
                    # Confirm with user before executing
                    if confirm:
                        try:
                            conn = psycopg2.connect(
                            user=USER,
                            password=PASSWORD,
                            host=HOST,
                            port=PORT,
                            dbname=DBNAME
                        )
                            cur = conn.cursor()
                            update_sql = "UPDATE poultry_health_records SET case_status = 'Close', case_complete_reason = %s WHERE case_id = %s"
                            cur.execute(update_sql, (case_complete_reason, case_id))
                            conn.commit()
                            st.success("Case status updated to Close.")
                            # Refresh the case_id_list after update
                            # cur.execute("SELECT case_id FROM poultry_health_records WHERE case_status IS NULL OR case_status = ''")
                            # case_id_rows = cur.fetchall()
                            # # case_id_list = [row[0] for row in case_id_rows]
                            # st.session_state.case_id_list = [row[0] for row in case_id_rows]

                            on_status_change()

                            
                            st.session_state.record_found = False  # Reset form state
                            st.info("Press continue to select other case id.")

                            continue_btn = st.form_submit_button("Continue")
                            if continue_btn:    
                                # Force a rerun to update the selectbox
                                status = "Open"
                                on_status_change()
                                st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")
                        finally:
                            if 'cur' in locals():
                                cur.close()
                            if 'conn' in locals():
                                conn.close()
                        st.success("Record updated successfully!")
                    else:
                        st.warning("Please confirm before submitting.")
                elif escalate_btn:
                    print("Escalate....")
                    if confirm:
                        try:
                            conn = psycopg2.connect(
                            user=USER,
                            password=PASSWORD,
                            host=HOST,
                            port=PORT,
                            dbname=DBNAME
                        )
                            cur = conn.cursor()
                            update_sql = "UPDATE poultry_health_records SET case_owner = 'Technical', case_complete_reason = %s WHERE case_id = %s"
                            cur.execute(update_sql, (case_complete_reason, case_id))
                            conn.commit()
                            st.success("Case status updated to Escalate.")
                          
                            on_status_change()

                            
                            st.session_state.record_found = False  # Reset form state
                            st.info("Press continue to select other case id.")

                            continue_btn = st.form_submit_button("Continue")
                            if continue_btn:    
                                # Force a rerun to update the selectbox
                                status = "Open"
                                on_status_change()
                                st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")
                        finally:
                            if 'cur' in locals():
                                cur.close()
                            if 'conn' in locals():
                                conn.close()
                        st.success("Record updated successfully!")
                    else:
                        st.warning("Please confirm before submitting.")


elif menu == "Technical Management":
    st.header("Technical Management")
    if 'selected_case' not in st.session_state:
            st.session_state.selected_case = None
 # Initialize session state for record_found and form fields
    if "record_found" not in st.session_state:
        st.session_state.record_found = False
    if "update_fields" not in st.session_state:
        st.session_state.update_fields = {}
    if "case_owner" not in st.session_state:
        st.session_state.case_owner = None

    st.session_state.case_owner = "Technical"
    st.session_state.status = "Open"
    on_status_change()

    case_status = st.radio(
    "Select Case Status",
    options=["Open", "Close"],
    horizontal=True,
    key="case_status",
    on_change=on_status_change  # Added callback
    )

    

    selected_case_id = st.selectbox("Select Case ID", options=st.session_state.case_id_list)
    st.session_state.selected_case = selected_case_id

    with st.form("sale_managemen_form"):
        fetch_btn = st.form_submit_button("Fetch Record")

        if fetch_btn:
            # Fetch the record from the database based on the selected case ID     
            #Supabase codes
            connection = psycopg2.connect(
                        user=USER,
                        password=PASSWORD,
                        host=HOST,
                        port=PORT,
                        dbname=DBNAME
                    )

            print("Connection successful!")
            # Create a cursor to execute SQL queries
            cursor = connection.cursor()

            cursor.execute(
                "SELECT body_weight, body_temperature, vaccination_records, symptoms, image_analysis,complete_status,case_status,case_owner,case_complete_reason FROM poultry_health_records WHERE case_id = %s",
                (selected_case_id,))
            row = cursor.fetchone()
            # Close the cursor and connection
            cursor.close()
            connection.close()
            print("Connection closed.")
            if row:
                st.session_state.record_found = True
                st.session_state.update_fields = {
                    "body_weight": row[0],
                    "body_temp": row[1],
                    "vaccines": row[2],
                    "symptoms": row[3],
                    "image_analysis": row[4],
                    "complete_status": row[5],
                    "case_status": row[6],
                    "case_owner": row[7],
                    "case_complete_reason": row[8]
                }
                st.success("Record found. You can now check the fields below.")          
            else:
                st.session_state.record_found = False
                st.session_state.update_fields = {}
                st.error("Record not found. Please check the ID.")
            
             # Only display the update form if a record was found
        if st.session_state.record_found:
            update_fields = st.session_state.update_fields
            case_id = st.text_input("Case ID", value=selected_case_id, disabled=True)
            new_body_weight = st.number_input("Body Weight (kg)", min_value=0.0, value=update_fields.get("body_weight", 0.0), key="update_weight", disabled=True)
            new_body_temp = st.number_input("Body Temperature (°C)", min_value=0.0, value=update_fields.get("body_temp", 0.0), key="update_temp", disabled=True)
            new_vaccines = st.text_input("Vaccination Records", value=update_fields.get("vaccines", ""), key="update_vaccines", disabled=True)
            new_symptoms = st.text_input("Symptoms", value=update_fields.get("symptoms", ""), key="update_symptoms", disabled=True)
            new_image_analysis = st.text_input("Image Analysis", value=update_fields.get("image_analysis", ""), key="update_image_analysis", disabled=True)
            uploaded_image = st.file_uploader("Upload New Image (optional)", type=["jpg", "jpeg", "png"], key="update_image", disabled=True)
            new_image_analysis = update_fields.get("image_analysis", "")
            complete_status = st.text_input("Complete Status", value=update_fields.get("complete_status", ""), key="update_complete_status", disabled=True)
            case_status = st.text_input("Case Status", value=update_fields.get("case_status", ""), key="update_case_status", disabled=True)
            case_owner = st.text_input("Case Owner", value=update_fields.get("case_owner", ""), key="update_case_owner", disabled=True)
            case_complete_reason = st.text_input("Case Complete Reason", value=update_fields.get("case_complete_reason", ""), key="update_case_complete_reason", disabled=False)

            if case_status == "Open":
                #Submit button for update
                confirm = st.checkbox("I confirm to submit and set this case as Close.")
                submit_btn = st.form_submit_button("Submit case")
              
                
                if submit_btn:
                    # Confirm with user before executing
                    if confirm:
                        try:
                            conn = psycopg2.connect(
                            user=USER,
                            password=PASSWORD,
                            host=HOST,
                            port=PORT,
                            dbname=DBNAME
                        )
                            cur = conn.cursor()
                            update_sql = "UPDATE poultry_health_records SET case_status = 'Close', case_complete_reason = %s WHERE case_id = %s"
                            cur.execute(update_sql, (case_complete_reason, case_id))
                            conn.commit()
                            st.success("Case status updated to Close.")
                          
                            on_status_change()

                            
                            st.session_state.record_found = False  # Reset form state
                            st.info("Press continue to select other case id.")

                            continue_btn = st.form_submit_button("Continue")
                            if continue_btn:    
                                # Force a rerun to update the selectbox
                                status = "Open"
                                on_status_change()
                                st.rerun()
                        except Exception as e:
                            st.error(f"Database error: {e}")
                        finally:
                            if 'cur' in locals():
                                cur.close()
                            if 'conn' in locals():
                                conn.close()
                        st.success("Record updated successfully!")
                    else:
                        st.warning("Please confirm before submitting.")






