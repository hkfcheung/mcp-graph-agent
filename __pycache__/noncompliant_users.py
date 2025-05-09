import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# Load SLACKBOT token from .env
load_dotenv()
SLACK_TOKEN = os.getenv("SLACKBOT")
if not SLACK_TOKEN:
    print("Error: SLACKBOT environment variable not set or .env file not found.")
    exit(1)
client = WebClient(token=SLACK_TOKEN)

# Dictionary of emails to names
user_info = {
    "ethan.cheung@dayonebio.com": "Ethan"
    # Add more users here if needed
    # "another.user@example.com": "Another User"
}

# File paths - ensure these paths are correct and accessible by the script
file_paths = [
    "/Users/ethancheung/Documents/AI/Hackathon/Druva Reactivation for Mac.docx",
    "/Users/ethancheung/Documents/AI/Hackathon/Druva Reactivation for Windows.docx"
]

def get_user_id_by_email(email_address, slack_client):
    """Look up Slack user ID from email address using the provided client."""
    try:
        response = slack_client.users_lookupByEmail(email=email_address)
        return response['user']['id']
    except SlackApiError as e:
        # Check for user_not_found error specifically
        if e.response['error'] == 'users_not_found':
            print(f"⚠️ User not found for email: {email_address}")
        else:
            print(f"❌ Error looking up {email_address}: {e.response['error']}")
        return None

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

def send_message_with_attachments(user_id, name, files_to_send, slack_client):
    """Send personalized message and attach files using files_upload_v2."""
    message_text = (
        f"Hi {name}, our records show that your laptop hasn't backed up in over 7 days. "
        "To stay compliant with our data protection policy, please follow the steps below to reactivate your backup client. "
        "If you're unable to complete this in [3 days], we'll need to schedule time with you directly to resolve it.\n\n"
        "_This message was sent on behalf of the IT Service Desk at Day One Bio._"
    )
    try:
        print(f"💬 Sending initial message to {name} ({user_id})...")
        response = slack_client.chat_postMessage(channel=user_id, text=message_text)
        thread_ts = str(response["ts"])
        print(f"📨 Message sent. Thread_ts: {thread_ts}")

        for path in files_to_send:
            if not os.path.exists(path):
                print(f"❌ File not found, skipping: {path}")
                continue

            file_name = os.path.basename(path)
            print(f"📎 Uploading {file_name} to {name} (channel: {user_id}) in thread {thread_ts}...")
            try:
                with open(path, "rb") as file_content:
                    upload_response = slack_client.files_upload_v2(
                        channel_id=user_id,      # Essential for DM visibility
                        file=file_content,
                        filename=file_name,
                        thread_ts=thread_ts,     # Essential for threading
                        title=file_name
                        # initial_comment=""  # <--- REMOVED THIS (or set to None explicitly)
                                                # If an empty string was causing issues, None might be better.
                                                # Or just remove it entirely if the SDK defaults it appropriately.
                    )
                
                print(f"DEBUG: Full upload response for {file_name}: {upload_response}")
                
                if upload_response.get("ok"):
                    print(f"📄 File '{file_name}' uploaded successfully according to API.")
                    slack_file_obj = upload_response.get("file", {})
                    if slack_file_obj:
                        print(f"   Slack File ID: {slack_file_obj.get('id')}")
                        print(f"   Shared to Channels: {slack_file_obj.get('channels')}")
                        print(f"   Shared to Groups: {slack_file_obj.get('groups')}")
                        print(f"   Shared to IMs (DMs): {slack_file_obj.get('ims')}")
                        if user_id in slack_file_obj.get('ims', []):
                            print(f"   ✅ File shared with user {user_id} in their DMs.")
                        else:
                            print(f"   ⚠️ File NOT shared with user {user_id} in their DMs via 'ims' field.")
                        print(f"   Permalink: {slack_file_obj.get('permalink')}")
                    else:
                        print(f"   ⚠️ File object not found in successful API response.")
                else:
                    print(f"⚠️ Error response during upload of {file_name}: {upload_response.get('error', 'Unknown error')}")
                    print(f"Full error response: {upload_response}")

            except SlackApiError as e_file:
                print(f"❌ Slack API Error uploading file {file_name}: {e_file.response['error']}")
                print(f"Full Slack API error response: {e_file.response}")
            except Exception as e_gen: # Catching the specific error source
                print(f"❌ An unexpected error occurred uploading file {file_name}: {str(e_gen)}")
                # If the error is "multiple values for keyword argument 'channel_id'",
                # we can add more specific debug info here later.

        print(f"✅ Message and file upload process completed for {name} ({user_id})")
    except SlackApiError as e_msg:
        print(f"❌ Error sending initial message to {name}: {e_msg.response['error']}")
    except Exception as e_gen_msg:
        print(f"❌ An unexpected error occurred sending message to {name}: {str(e_gen_msg)}")




# --- Main script execution ---
if __name__ == "__main__":
    print("Starting script...")
    if not user_info:
        print("No users defined in user_info. Exiting.")
        exit(0)

    if not file_paths:
        print("No file_paths defined. Messages will be sent without attachments.")
        # You might want to exit here or handle this case specifically
        # exit(0)

    # Verify all file paths exist before starting the loop
    all_files_exist = True
    for f_path in file_paths:
        if not os.path.exists(f_path):
            print(f"❌ Critical: File path does not exist: {f_path}. Please check your file_paths list.")
            all_files_exist = False
    if not all_files_exist and file_paths: # only fail if files were expected
        print("One or more specified files do not exist. Aborting.")
        exit(1)


    for email, name in user_info.items():
        print(f"\nProcessing user: {name} ({email})")
        slack_id = get_user_id_by_email(email, client) # Pass client here
        if slack_id:
            # Pass the global 'client' object to the function
            send_message_with_attachments(slack_id, name, file_paths, client)
        else:
            print(f"Could not send message to {name} as Slack ID was not found.")
    
    print("\nScript finished.")