import os
import requests
from bs4 import BeautifulSoup
import gradio as gr
import openai
from dotenv import load_dotenv
import time
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import io
import uuid
import anthropic
import logging

# Load environment variables for OpenAI API key, Google Sheets, and Anthropic API key
load_dotenv()
openai_api_key = os.environ.get('LUNAS_OPENAI_API_KEY')
anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY')

# Set up logging
logging.basicConfig(filename='cv_adaptation_log.txt', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Google Sheets configuration
SERVICE_ACCOUNT_FILE = r'C:\Users\chuck\OneDrive\Desktop\Dev\luna_sesh_sm\autopostsm-6663e9622756.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
SHEET_ID = '1aUmm30Ht0hsMWA4lAtT-0oW4xdlB6ivAD6mLICMFS74'
SHEET_RANGE = 'control1'

# Initialize the Sheets API client
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Initialize the Drive API client
drive_service = build('drive', 'v3', credentials=creds)

# Initialize the Docs API client
docs_service = build('docs', 'v1', credentials=creds)

# Initialize the Anthropic client
anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)

# Google Drive saving folder
LUNA_JOB_SEEKER_FOLDER_ID = '1WqaDnTVAKeIixv2L0ml8YWNTkE7K0Pl7'

def get_folder_id(service, folder_name, parent_folder_id='root'):
    """Get the ID of a folder with the given name in the specified parent folder."""
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_folder_id}' in parents and trashed = false"
    response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    folders = response.get('files', [])
    print(f"Searching for folder '{folder_name}' in parent folder ID '{parent_folder_id}'")
    print(f"Folders found: {folders}")
    if folders:
        folder_id = folders[0]['id']
        print(f"Folder '{folder_name}' found with ID '{folder_id}'")
        return folder_id
    else:
        print(f"Folder '{folder_name}' not found in parent folder ID '{parent_folder_id}'. Creating folder...")
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')
        print(f"Folder '{folder_name}' created with ID '{folder_id}'")
        return folder_id

def get_job_details_from_sheet(job_id):
    # Find the row with the specified job ID
    result = sheet.values().get(spreadsheetId=SHEET_ID, range=SHEET_RANGE).execute()
    rows = result.get('values', [])
    job_details_row = next((row for row in rows if row[0] == job_id), None)
    if job_details_row is None:
        return {}  # Return an empty dictionary if job details not found
    # Extract the job details from the row
    job_details = {
        'company': job_details_row[1],
        'position': job_details_row[2],
        'contact': job_details_row[3],
        'email': job_details_row[4]
    }
    return job_details

def extract_and_update_job_details(job_description, job_id):
    # Get the entire response using Anthropic's Haiku model
    details = []
    for detail in ["company", "position", "contact", "email"]:
        response = anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            temperature=.1,
            messages=[
                {
                    "role": "user",
                    "content": f"Help me identify the {detail} from this text: {job_description} just print the answer nothing else as this is part of a bigger automation and will break the json EG do not do this The company mentioned in the text is B3 Systems dont mention The company mentioned in the text is just the company name. instead of The company mentioned in the text is Tata Consultancy Services just do Tata Consultancy like that for all the questions I dont want extra text, for email do not add any text just give me the email, for the contact name do not add any extra text just position name and last name no extra text, for the role or position do not add any extra text just add the job position    "
                }
            ]
        )
        print(f"{detail.capitalize()} response: {response}")
        # Extract the text from the response
        extracted_detail = ""
        for content_block in response.content:
            extracted_detail += content_block.text.strip() + " "
        extracted_detail = extracted_detail.strip()  # Remove any trailing whitespace
        details.append(extracted_detail)
        time.sleep(5)  # Wait for 5 seconds before making the next API call
    # Print the extracted details for debugging
    print(f"Extracted details: {details}")
    # Return the extracted details instead of updating the sheet
    return details

def scrape_job_description(url):
    if not url.startswith("http"):
        raise ValueError("Invalid URL. Please provide a valid job listing URL.")

    response = requests.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # Attempt to find the main content of the job description
    main_content = soup.find('main') or soup.find(id='main-content') or soup.find(class_='job-description') or soup.body

    if main_content is None:
        return "Main content element not found. Please check the page structure."

    # Get the text content of the main job description, stripping any excess whitespace
    job_description = ' '.join(main_content.get_text(strip=True, separator=' ').split())

    return job_description

def generate_and_save_cover_letter(job_summary, position, company_name):
    try:
        # Generate the cover letter content
        cover_letter_content = generate_cover_letter(job_summary, position)
        if not cover_letter_content or cover_letter_content.startswith("Error"):
            return f"Failed to generate cover letter: {cover_letter_content}", None

        # Create a new Google Doc for the cover letter
        doc_title = f"Cover Letter for {position} at {company_name}"
        doc = docs_service.documents().create(body={'title': doc_title}).execute()
        doc_id = doc.get('documentId')

        # Add the cover letter content to the document
        requests = [{
            'insertText': {
                'location': {
                    'index': 1,
                },
                'text': cover_letter_content
            }
        }]
        docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()

        # Move the Google Doc to the company folder
        parent_folder_id = LUNA_JOB_SEEKER_FOLDER_ID
        company_folder_id = get_folder_id(drive_service, company_name, parent_folder_id=parent_folder_id)
        drive_service.files().update(fileId=doc_id, addParents=company_folder_id, removeParents='root', fields='id, parents').execute()

        # Get the shareable link of the Google Doc
        shareable_link = f"https://docs.google.com/document/d/{doc_id}/edit"
        return f"Cover letter saved to Google Docs: {shareable_link}", shareable_link, doc_id
    except Exception as e:
        return f"An error occurred while creating the cover letter: {e}", None, None

def generate_cover_letter(job_summary, position):
    headers = {
        'Authorization': f'Bearer {openai_api_key}',
        'Content-Type': 'application/json',
        'OpenAI-Beta': 'assistants=v1'
    }

    thread_response = requests.post(
        'https://api.openai.com/v1/threads',
        headers=headers
    )
    if thread_response.status_code != 200:
        return f"Error creating thread: {thread_response.text}"
    thread_id = thread_response.json().get('id')

    message_data = {
        'role': 'user',
        'content': f"Write a cover letter for the position of {position} based on the following job summary: {job_summary} keep it short professional and on a highschool conversational level"
    }
    message_response = requests.post(
        f'https://api.openai.com/v1/threads/{thread_id}/messages',
        headers=headers,
        json=message_data
    )
    if message_response.status_code != 200:
        return f"Error adding message to thread: {message_response.text}"

    run_data = {
        'assistant_id': 'asst_arQMZ4ZzvGIFVTeEh2fSFyj1'
    }
    run_response = requests.post(
        f'https://api.openai.com/v1/threads/{thread_id}/runs',
        headers=headers,
        json=run_data
    )
    if run_response.status_code != 200:
        return f"Error running assistant on thread: {run_response.text}"

    # Wait for the run to complete
    run_id = run_response.json().get('id')
    run_status = run_response.json().get('status')
    while run_status != 'completed':
        run_response = requests.get(
            f'https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}',
            headers=headers
        )
        run_status = run_response.json().get('status')
        time.sleep(1)  # Wait before checking again

    # Retrieve the final response from the assistant
    final_response = requests.get(
        f'https://api.openai.com/v1/threads/{thread_id}/messages',
        headers=headers
    )
    assistant_messages = [msg for msg in final_response.json().get('data', []) if msg.get('role') == 'assistant']
    if assistant_messages:
        cover_letter = assistant_messages[-1].get('content', [{}])[0].get('text', {}).get('value', '')
        return cover_letter
    else:
        return "No cover letter generated."

def update_row_in_sheet(job_id, values):
    # Load the credentials and initialize the Sheets API client
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)

    # Find the row number of the row with the specified ID
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=SHEET_RANGE
    ).execute()
    rows = result.get('values', [])
    row_number = next((i + 1 for i, row in enumerate(rows) if row[0] == job_id), None)

    if row_number is None:
        # Append the data to the end of the sheet if the row with the ID is not found
        body = {
            'values': [values]
        }
        result = service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range=SHEET_RANGE,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
    else:
        # Update the row in the sheet if the row with the ID is found
        range_name = f'{SHEET_RANGE}!A{row_number}'
        value_input_option = 'RAW'
        body = {
            'values': [values]
        }
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=range_name,
            valueInputOption=value_input_option,
            body=body
        ).execute()

def summarize_job_description(job_description):
    # Set up the headers with your OpenAI API key
    headers = {
        'Authorization': f'Bearer {openai_api_key}',
        'Content-Type': 'application/json',
        'OpenAI-Beta': 'assistants=v1'
    }

    # Create a new thread
    thread_response = requests.post(
        'https://api.openai.com/v1/threads', headers=headers
    )
    if thread_response.status_code != 200:
        return f"Error creating thread: {thread_response.text}"
    thread_id = thread_response.json().get('id')

    # Add the job description as a message to the thread
    message_data = {
        'role': 'user',
        'content': f"hey can u give me a job summary of this position plz {job_description}"
    }
    message_response = requests.post(
        f'https://api.openai.com/v1/threads/{thread_id}/messages',
        headers=headers,
        json=message_data
    )
    if message_response.status_code != 200:
        return f"Error adding message to thread: {message_response.text}"

    # Run the assistant on the thread to generate a summary
    run_data = {
        'assistant_id': 'asst_arQMZ4ZzvGIFVTeEh2fSFyj1'
    }
    run_response = requests.post(
        f'https://api.openai.com/v1/threads/{thread_id}/runs',
        headers=headers,
        json=run_data
    )
    if run_response.status_code != 200:
        return f"Error running assistant on thread: {run_response.text}"

    # Wait for the run to complete
    run_id = run_response.json().get('id')
    run_status = run_response.json().get('status')
    while run_status != 'completed':
        run_response = requests.get(
            f'https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}',
            headers=headers
        )
        run_status = run_response.json().get('status')
        time.sleep(1)  # Wait before checking again

    # Retrieve the final response from the assistant
    final_response = requests.get(
        f'https://api.openai.com/v1/threads/{thread_id}/messages',
        headers=headers
    )
    assistant_messages = [msg for msg in final_response.json().get('data', []) if msg.get('role') == 'assistant']
    if assistant_messages:
        summary = assistant_messages[-1].get('content', [{}])[0].get('text', {}).get('value', '')
        return summary
    else:
        return "No summary found."

def choose_cv_based_on_summary(job_summary):
    # Set up the headers with your OpenAI API key
    headers = {
        'Authorization': f'Bearer {openai_api_key}',
        'Content-Type': 'application/json',
        'OpenAI-Beta': 'assistants=v1'
    }

    # Create a new thread
    thread_response = requests.post(
        'https://api.openai.com/v1/threads', headers=headers
    )
    if thread_response.status_code != 200:
        return f"Error creating thread: {thread_response.text}"
    thread_id = thread_response.json().get('id')

    # Add the job summary as a message to the thread
    message_data = {
        'role': 'user',
        'content': f"Based on what you know about Donovan, which of their CVs should we use to apply to this position? Please just answer with 'AI CV' or 'UX CV' or other custom CV please Specify wich you can also tell me that 'Its not a good Fit' .\n\nJob Summary: {job_summary}"
    }
    message_response = requests.post(
        f'https://api.openai.com/v1/threads/{thread_id}/messages',
        headers=headers,
        json=message_data
    )
    if message_response.status_code != 200:
        return f"Error adding message to thread: {message_response.text}"

    # Run the assistant on the thread to get the CV recommendation
    run_data = {
        'assistant_id': 'asst_arQMZ4ZzvGIFVTeEh2fSFyj1'
    }
    run_response = requests.post(
        f'https://api.openai.com/v1/threads/{thread_id}/runs',
        headers=headers,
        json=run_data
    )
    if run_response.status_code != 200:
        return f"Error running assistant on thread: {run_response.text}"

    # Wait for the run to complete
    run_id = run_response.json().get('id')
    run_status = run_response.json().get('status')
    while run_status != 'completed':
        run_response = requests.get(
            f'https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}',
            headers=headers
        )
        run_status = run_response.json().get('status')
        time.sleep(1)  # Wait before checking again

    # Retrieve the final response from the assistant
    final_response = requests.get(
        f'https://api.openai.com/v1/threads/{thread_id}/messages',
        headers=headers
    )
    assistant_messages = [msg for msg in final_response.json().get('data', []) if msg.get('role') == 'assistant']
    if assistant_messages:
        cv_recommendation = assistant_messages[-1].get('content', [{}])[0].get('text', {}).get('value', '')
        return cv_recommendation
    else:
        return "No CV recommendation found."

def adapt_cv_for_job_role(selected_cv, job_summary, company_name):
    try:
        # Set up the headers with your OpenAI API key
        headers = {
            'Authorization': f'Bearer {openai_api_key}',
            'Content-Type': 'application/json',
            'OpenAI-Beta': 'assistants=v1'
        }
        # Create a new thread
        thread_response = requests.post(
            'https://api.openai.com/v1/threads', headers=headers
        )
        if thread_response.status_code != 200:
            return f"Error creating thread: {thread_response.text}", None
        thread_id = thread_response.json().get('id')
        # Add the request to adapt the CV as a message to the thread
        message_data = {
            'role': 'user',
            'content': f"Hey dude,first of all no chitty chat. Do not answer with anything else that what Im asking eg: This version emphasizes all the requested skills and responsibilities from the job description, ensuring Donovan's expertise and suitability for the role are clear and align with TCS's needs. Dont do that just the cv . ,,, Adapt the {selected_cv} for this job role {job_summary}. I want it in this order: personal info, Objective, Work Goals, Skills, Skills applied on work, Experience, how I over come obtacles, salary expectations, references. Use all key words and take into consideration eye heat maps for the CV.,,, Use simple conversational highschool grade language.,,, Your end goal is This CV should capture the recruiter's attention and match the job requirements effectively.,,, I want the CV to be professional and to came as if me Donovan wrote it not that u dude."
        }
        message_response = requests.post(
            f'https://api.openai.com/v1/threads/{thread_id}/messages',
            headers=headers,
            json=message_data
        )
        if message_response.status_code != 200:
            return f"Error adding message to thread: {message_response.text}", None
        # Run the assistant on the thread to get the adapted CV
        run_data = {
            'assistant_id': 'asst_arQMZ4ZzvGIFVTeEh2fSFyj1'
        }
        run_response = requests.post(
            f'https://api.openai.com/v1/threads/{thread_id}/runs',
            headers=headers,
            json=run_data
        )
        if run_response.status_code != 200:
            return f"Error running assistant on thread: {run_response.text}", None
        # Wait for the run to complete
        run_id = run_response.json().get('id')
        run_status = run_response.json().get('status')
        while run_status != 'completed':
            run_response = requests.get(
                f'https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}',
                headers=headers
            )
            run_status = run_response.json().get('status')
            time.sleep(1)  # Wait before checking again
        # Retrieve the final response from the assistant
        logging.info("Retrieving adapted CV content from the assistant")
        final_response = requests.get(
            f'https://api.openai.com/v1/threads/{thread_id}/messages',
            headers=headers
        )
        assistant_messages = [msg for msg in final_response.json().get('data', []) if msg.get('role') == 'assistant']
        if assistant_messages:
            adapted_cv_content = assistant_messages[-1].get('content', [{}])[0].get('text', {}).get('value', '')
            logging.info("Adapted CV content retrieved successfully")
            print(f"Adapted CV content: {adapted_cv_content}")  # Print the adapted CV content
        else:
            logging.error("No adapted CV content found")
            return "No adapted CV generated.", None
        # Create a new Google Doc with the adapted CV content
        doc_title = f"{selected_cv}_{company_name}"
        doc_requests = []
        # Parse the adapted CV content and create requests for formatting
        for line in adapted_cv_content.split('\n'):
            if line.startswith('### '):
                # Add a heading
                heading_text = line.strip('### ')
                doc_requests.append({'insertText': {'text': heading_text + '\n', 'location': {'index': 1}}})
                doc_requests.append({'updateParagraphStyle': {'paragraphStyle': {'namedStyleType': 'HEADING_1'}, 'fields': 'namedStyleType', 'range': {'startIndex': 1, 'endIndex': len(heading_text) + 1}}})
            elif line.startswith('**') and line.endswith('**'):
                # Add a subheading
                subheading_text = line.strip('**')
                doc_requests.append({'insertText': {'text': subheading_text + '\n', 'location': {'index': 1}}})
                doc_requests.append({'updateParagraphStyle': {'paragraphStyle': {'namedStyleType': 'HEADING_2'}, 'fields': 'namedStyleType', 'range': {'startIndex': 1, 'endIndex': len(subheading_text) + 1}}})
            elif line.startswith('- '):
                # Add a list item
                doc_requests.append({'insertText': {'text': line + '\n', 'location': {'index': 1}}})
            else:
                # Add normal text
                doc_requests.append({'insertText': {'text': line + '\n', 'location': {'index': 1}}})
        # Reverse the order of the doc_requests list
        doc_requests.reverse()
        # Create the document with the title
        doc = docs_service.documents().create(body={'title': doc_title}).execute()
        doc_id = doc.get('documentId')
        logging.info(f"Google Doc created with ID: {doc_id}")
        # Batch update the document with formatted text
        docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': doc_requests}).execute()
        # Create a folder for the company in Google Drive if it doesn't exist
        parent_folder_id = LUNA_JOB_SEEKER_FOLDER_ID
        company_folder_id = get_folder_id(drive_service, company_name, parent_folder_id=parent_folder_id)
        # Move the Google Doc to the company folder
        drive_service.files().update(fileId=doc_id, addParents=company_folder_id, removeParents='root', fields='id, parents').execute()
        logging.info(f"Google Doc moved to company folder with ID: {company_folder_id}")
        # Get the shareable link of the Google Doc
        shareable_link = f"https://docs.google.com/document/d/{doc_id}/edit"
        return f"Adapted CV saved to Google Docs: {shareable_link}", shareable_link, doc_id
    except Exception as e:
        logging.error(f"An error occurred while creating the Google Doc: {e}")
        return f"An error occurred while creating the Google Doc: {e}", None, None

def convert_docs_to_pdf(cv_doc_id, cover_letter_doc_id, folder_id):
    try:
        # Export the CV and cover letter Google Docs as PDF
        cv_pdf_content = drive_service.files().export(fileId=cv_doc_id, mimeType='application/pdf').execute()
        cover_letter_pdf_content = drive_service.files().export(fileId=cover_letter_doc_id, mimeType='application/pdf').execute()

        # Create a new file in Google Drive with the PDF content for the CV
        cv_file_metadata = {
            'name': 'CV_Donovan_Cayetano.pdf',
            'parents': [folder_id]
        }
        cv_media = MediaIoBaseUpload(io.BytesIO(cv_pdf_content), mimetype='application/pdf')
        cv_pdf_file = drive_service.files().create(body=cv_file_metadata, media_body=cv_media, fields='id').execute()

        # Create a new file in Google Drive with the PDF content for the cover letter
        cover_letter_file_metadata = {
            'name': 'Cover_Letter_Donovan_Cayetano.pdf',
            'parents': [folder_id]
        }
        cover_letter_media = MediaIoBaseUpload(io.BytesIO(cover_letter_pdf_content), mimetype='application/pdf')
        cover_letter_pdf_file = drive_service.files().create(body=cover_letter_file_metadata, media_body=cover_letter_media, fields='id').execute()

        # Get the shareable links of the PDF files
        cv_pdf_link = f"https://drive.google.com/file/d/{cv_pdf_file.get('id')}/view"
        cover_letter_pdf_link = f"https://drive.google.com/file/d/{cover_letter_pdf_file.get('id')}/view"
        return f"CV PDF saved to Google Drive: {cv_pdf_link}\nCover letter PDF saved to Google Drive: {cover_letter_pdf_link}"
    except Exception as e:
        return f"An error occurred while converting to PDF: {e}"

def scrape_and_display_job_description(url_or_text, input_type):
    try:
        if input_type == "Scrape":
            job_description = scrape_job_description(url_or_text)
        else:
            job_description = url_or_text
        
        summary = summarize_job_description(job_description)
        # Generate a unique ID for the job application
        job_id = str(uuid.uuid4())
        # Extract job details and do not update the sheet immediately
        extracted_details = extract_and_update_job_details(job_description, job_id)
        # Generate a cover letter
        cover_letter = generate_cover_letter(summary, extracted_details[1])
        # Choose the CV based on the job summary
        cv_used = choose_cv_based_on_summary(summary)
        # Adapt the CV for the job role and get the adapted CV content and Google Doc link
        adapted_cv_response, adapted_cv_link, adapted_cv_doc_id = adapt_cv_for_job_role(cv_used, summary, extracted_details[0])
        adapted_cv_content = adapted_cv_response.split("Adapted CV saved to Google Docs: ")[1].strip()
        # Generate and save the cover letter in the same folder as the CV
        cover_letter_response, cover_letter_link, cover_letter_doc_id = generate_and_save_cover_letter(summary, extracted_details[1], extracted_details[0])
        print(cover_letter_response)
        if cover_letter_link:
            print(f"Cover letter saved at: {cover_letter_link}")
        # Convert the CV and cover letter Google Docs to PDF
        parent_folder_id = LUNA_JOB_SEEKER_FOLDER_ID
        company_folder_id = get_folder_id(drive_service, extracted_details[0], parent_folder_id=parent_folder_id)
        pdf_conversion_response = convert_docs_to_pdf(adapted_cv_doc_id, cover_letter_doc_id, company_folder_id)
        print(pdf_conversion_response)
        # Prepare the values to be inserted into Google Sheets, including the extracted details, CV recommendation, Luna status, adapted CV content, and CV creation status
        values = [
            [job_id, extracted_details[0], extracted_details[1], summary, cover_letter, adapted_cv_content, "", extracted_details[2], extracted_details[3], "", "CV Created", "", cv_used, adapted_cv_link, cover_letter_link]
        ]
        # Insert the data into Google Sheets
        body = {
            'values': values
        }
        result = sheet.values().append(
            spreadsheetId=SHEET_ID,
            range=SHEET_RANGE,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        return f"Summary: {summary}\n\nCompany: {extracted_details[0]}\nPosition: {extracted_details[1]}\nContact: {extracted_details[2]}\nEmail: {extracted_details[3]}\nCV Used: {cv_used}\nAdapted CV Content: {adapted_cv_content}\nCover Letter:\n{cover_letter}\nAdapted CV Google Doc Link: {adapted_cv_link}\nCover Letter Google Doc Link: {cover_letter_link}"
    except Exception as e:
        return f"An error occurred: {e}"

# Gradio interface
input_type = gr.Radio(["Scrape", "Input Info"], label="Input Type")
url_or_text = gr.Textbox(lines=2, placeholder="Enter job posting URL or job description text...")

interface = gr.Interface(
    fn=scrape_and_display_job_description,
    inputs=[url_or_text, input_type],
    outputs="text",
    title="Luna's Job Hunt Tool Bolos Edition",
    description="Paste a job posting URL or enter job description text to process and generate CV and cover letter."
)

if __name__ == "__main__":
    interface.launch(share=True, inbrowser=True)
