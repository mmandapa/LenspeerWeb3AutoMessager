const axios = require('axios');
const sqlite3 = require('sqlite3').verbose();
const db = new sqlite3.Database('sent_profiles.db');

async function sendMessage(profileId, messageContent, apiInfo) {
    try {
        const response = await axios.post(apiInfo.message_endpoint, {
            profile_id: profileId,
            message: messageContent,
        }, {
            headers: {
                'Authorization': `Bearer ${apiInfo.auth_token}`,
                'Content-Type': 'application/json',
            },
        });
        console.log(`Message sent to profile ${profileId}. Response: ${response.data}`);
        return response.data;
    } catch (error) {
        console.error(`Error sending message to profile ${profileId}: ${error.message}`);
    }
}

function getProfilesToMessage() {
    return new Promise((resolve, reject) => {
        db.all("SELECT profile_id, full_handle, display_name, api_info FROM sent_profiles WHERE engagement_score > ?",
            [0], (err, rows) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(rows);
                }
            });
    });
}

(async function main() {
    const messageContent = "Hello! Check out Web3Names.AI, where you can claim your own web3 domain!";
    const profiles = await getProfilesToMessage();

    for (const profile of profiles) {
        const apiInfo = JSON.parse(profile.api_info);
        await sendMessage(profile.profile_id, messageContent, apiInfo);
    }

    db.close();
})();
