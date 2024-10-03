import time
import logging
import requests
import json
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# Configure logging
logging.basicConfig(filename='lenspeer_automation_log.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

API_BASE_URL = "https://api-v2.lens.dev/"

# Set up SQLite database
def setup_database():
    conn = sqlite3.connect('sent_profiles.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sent_profiles (
            profile_id TEXT PRIMARY KEY,
            full_handle TEXT,
            display_name TEXT,
            followers INTEGER,
            following INTEGER,
            interests_count INTEGER,
            api_info TEXT,
            engagement_score REAL
        )
    ''')
    # Create wallets table to store wallet data
    c.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            id TEXT PRIMARY KEY,
            name TEXT,
            homepage TEXT,
            image_id TEXT,
            mobile_link TEXT,
            desktop_link TEXT,
            chains TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Function to reset the database if the schema is incorrect
def reset_database():
    conn = sqlite3.connect('sent_profiles.db')
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS sent_profiles")
    c.execute("DROP TABLE IF EXISTS wallets")  # Drop wallets table
    setup_database()  # Recreate both tables
    conn.close()

# Function to check if the profile has already been messaged
def has_sent_message(profile_id):
    conn = sqlite3.connect('sent_profiles.db')
    c = conn.cursor()
    c.execute("SELECT profile_id FROM sent_profiles WHERE profile_id = ?", (profile_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

# Function to add the profile_id and API info to the sent profiles database
def add_sent_profile(profile_info, engagement_score=0):
    conn = sqlite3.connect('sent_profiles.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO sent_profiles 
                 (profile_id, full_handle, display_name, followers, following, interests_count, api_info, engagement_score) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (profile_info["profile_id"], profile_info["full_handle"], profile_info["display_name"],
               profile_info["followers"], profile_info["following"], profile_info["interests_count"],
               json.dumps(profile_info["api_info"]), engagement_score))
    conn.commit()
    conn.close()

# Function to store wallet data in the database
def store_wallets(wallets):
    conn = sqlite3.connect('sent_profiles.db')
    c = conn.cursor()
    for wallet in wallets:
        c.execute('''INSERT OR IGNORE INTO wallets (id, name, homepage, image_id, mobile_link, desktop_link, chains)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', (
            wallet['id'],
            wallet['name'],
            wallet['homepage'],
            wallet['image_id'],
            wallet['mobile_link'],
            wallet['desktop_link'],
            json.dumps(wallet['chains'])  # Store chains as JSON
        ))
    conn.commit()
    conn.close()

# AI Function to predict engagement score based on profile data
def predict_engagement_score(profile_info):
    features = pd.DataFrame([{
        'followers': profile_info['followers'],
        'following': profile_info['following'],
        'interests_count': profile_info['interests_count']
    }])

    model = RandomForestClassifier()  # Pre-trained model (replace with actual model)
    engagement_score = model.predict(features)[0]  # Predict engagement score
    return engagement_score

# GraphQL query to get profiles from the community page
explore_publications_query = """
query ExplorePublications($request: ExplorePublicationRequest!) {
  explorePublications(request: $request) {
    items {
      ... on Post {
        id
        by {
          handle {
            fullHandle
          }
          name
          stats {
            totalFollowers
            totalFollowing
          }
          interests
        }
      }
    }
  }
}
"""

# GraphQL query to fetch wallet data
wallets_query = """
query GetWallets {
    wallets {
        id
        name
        homepage
        image_id
        mobile_link
        desktop_link
        chains
    }
}
"""

# Function to fetch wallets and store them in the database
def fetch_and_store_wallets():
    url = f"{API_BASE_URL}graphql"
    headers = {
        "Content-Type": "application/json"
    }
    json_data = {
        "query": wallets_query
    }

    try:
        response = requests.post(url, json=json_data, headers=headers)
        response.raise_for_status()
        data = response.json()

        wallets = data['data']['wallets']
        store_wallets(wallets)
        logging.info(f"Stored {len(wallets)} wallets in the database.")
    except Exception as e:
        logging.error(f"Error fetching wallets: {e}")

# Function to fetch profiles from the community page
def get_community_profiles(auth_token):
    url = f"{API_BASE_URL}graphql"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    variables = {
        "request": {
            "sortCriteria": "LATEST",
            "limit": 10
        }
    }

    json_data = {
        "query": explore_publications_query,
        "variables": variables
    }

    try:
        response = requests.post(url, json=json_data, headers=headers)
        response.raise_for_status()
        data = response.json()

        profiles = []
        for item in data['data']['explorePublications']['items']:
            profile = item['by']
            profile_info = {
                "profile_id": item['id'],
                "full_handle": profile['handle']['fullHandle'],
                "display_name": profile['name'],
                "followers": profile['stats']['totalFollowers'],
                "following": profile['stats']['totalFollowing'],
                "interests_count": len(profile.get('interests', [])),
                "api_info": {
                    "auth_token": auth_token,
                    "profile_endpoint": f"{API_BASE_URL}profile/{item['id']}",
                    "message_endpoint": f"{API_BASE_URL}messages/send"
                }
            }
            engagement_score = predict_engagement_score(profile_info)
            profile_info["engagement_score"] = engagement_score
            profiles.append(profile_info)

        logging.info(f"Extracted {len(profiles)} profiles from the community page.")
        return profiles
    except Exception as e:
        logging.error(f"Error fetching profiles from the community page: {e}")
        return []

# Function to send a message to a profile via API
def send_message_to_profile(profile_id, message_content, profile_api_info):
    try:
        url = profile_api_info["message_endpoint"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {profile_api_info['auth_token']}"
        }
        payload = {
            "profile_id": profile_id,
            "message": message_content
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 400:
            logging.error(f"Bad Request: {response.text}")
        response.raise_for_status()

        logging.info(f"Message sent to profile {profile_id}.")
    except requests.RequestException as e:
        logging.error(f"Error sending message to profile {profile_id}: {str(e)}")

# Function to get all stored profiles from the database for messaging
def get_stored_profiles():
    conn = sqlite3.connect('sent_profiles.db')
    c = conn.cursor()
    c.execute(
        "SELECT profile_id, full_handle, display_name, api_info, engagement_score FROM sent_profiles ORDER BY engagement_score DESC")
    profiles = c.fetchall()
    conn.close()
    return profiles

# Main function to automate the process with looping feature
def main(auth_token, loop_delay=600):
    setup_database()  # Setup the database
    message_content = "Hello! Check out Web3Names.AI, where you can claim your own web3 domain!"

    # Fetch wallet data
    fetch_and_store_wallets()  # Fetch and store wallets

    while True:  # Loop indefinitely, or until a certain condition is met
        try:
            logging.info("Starting a new loop iteration with community profiles...")
            profiles = None
            for attempt in range(3):  # Retry up to 3 times
                try:
                    profiles = get_community_profiles(auth_token)
                    if profiles:
                        break  # Exit retry loop on success
                except Exception as e:
                    logging.error(f"Attempt {attempt + 1}: {str(e)}")
                    time.sleep(2)  # Wait before retrying

            if profiles:
                for profile_info in profiles:
                    if not has_sent_message(profile_info['profile_id']):  # Check if we have already sent a message
                        logging.info(
                            f"Preparing to send message to profile {profile_info['display_name']} with engagement score {profile_info['engagement_score']}")

                        add_sent_profile(profile_info, profile_info['engagement_score'])
                        send_message_to_profile(profile_info['profile_id'], message_content, profile_info['api_info'])

                        time.sleep(2)

                stored_profiles = get_stored_profiles()
                for profile_id, full_handle, display_name, api_info_str, engagement_score in stored_profiles:
                    api_info = json.loads(api_info_str)
                    logging.info(
                        f"Sending message to stored profile {display_name} with engagement score {engagement_score}")
                    send_message_to_profile(profile_id, message_content, api_info)
                    time.sleep(2)

                logging.info("Finished sending messages for this batch.")
            else:
                logging.error("Failed to fetch profiles after multiple attempts.")

            logging.info(f"Sleeping for {loop_delay} seconds before next iteration.")
            time.sleep(loop_delay)

        except Exception as e:
            logging.error(f"Error during loop iteration: {e}")

if __name__ == "__main__":
    auth_token = "YOUR_AUTH_TOKEN_HERE"  # Replace with your actual token
    main(auth_token)
