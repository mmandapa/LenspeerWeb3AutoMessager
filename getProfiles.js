const axios = require('axios');
const sqlite3 = require('sqlite3').verbose();
const db = new sqlite3.Database('sent_profiles.db');

// Fetch and store profiles from the Lens API
async function fetchAndStoreProfiles(authToken) {
    const query = `
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
    `;

    const variables = {
        request: {
            sortCriteria: "LATEST",
            limit: 10,
        },
    };

    try {
        const response = await axios.post('https://api-v2.lens.dev/graphql', {
            query,
            variables,
        }, {
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json',
            },
        });

        const profiles = response.data.data.explorePublications.items.map(item => ({
            profile_id: item.id,
            full_handle: item.by.handle.fullHandle,
            display_name: item.by.name,
            followers: item.by.stats.totalFollowers,
            following: item.by.stats.totalFollowing,
            interests_count: item.by.interests.length,
            api_info: {
                auth_token: authToken,
                profile_endpoint: `https://api-v2.lens.dev/profile/${item.id}`,
                message_endpoint: `https://api-v2.lens.dev/messages/send`
            }
        }));

        console.log(`Fetched ${profiles.length} profiles.`);

        // Store profiles in the database
        profiles.forEach(profile => {
            db.run(`INSERT OR IGNORE INTO sent_profiles (profile_id, full_handle, display_name, followers, following, interests_count, api_info) VALUES (?, ?, ?, ?, ?, ?, ?)`,
                [profile.profile_id, profile.full_handle, profile.display_name, profile.followers, profile.following, profile.interests_count, JSON.stringify(profile.api_info)]);
        });

    } catch (error) {
        console.error(`Error fetching profiles: ${error.message}`);
    }
}

// Fetch and store wallets from the GraphQL response
async function fetchAndStoreWallets(authToken) {
    const walletsData = [
        {
            "id": "c57ca95b47569778a828d19178114f4db188b89b763c899ba0be274e97267d96",
            "name": "MetaMask",
            "homepage": "https://metamask.io/",
            "image_id": "018b2d52-10e9-4158-1fde-a5d5bac5aa00",
            "mobile_link": "metamask://",
            "app_store": "https://apps.apple.com/us/app/metamask/id1438144202",
            "play_store": "https://play.google.com/store/apps/details?id=io.metamask",
            "chrome_store": "https://chrome.google.com/webstore/detail/metamask/nkbihfbeogaeaoehlefnkodbefgpgknn",
            "chains": ["eip155:1"]
        },
        {
            "id": "4622a2b2d6af1c9844944291e5e7351a6aa24cd7b23099efac1b2fd875da31a0",
            "name": "Trust Wallet",
            "homepage": "https://trustwallet.com/",
            "image_id": "7677b54f-3486-46e2-4e37-bf8747814f00",
            "mobile_link": "trust://",
            "app_store": "https://apps.apple.com/app/apple-store/id1288339409",
            "play_store": "https://play.google.com/store/apps/details?id=com.wallet.crypto.trustapp",
            "chains": ["cosmos:cosmoshub-4", "eip155:1", "eip155:137", "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"]
        }
    ];

    try {
        // Store wallet data in the database
        walletsData.forEach(wallet => {
            db.run(`INSERT OR IGNORE INTO wallets (id, name, homepage, image_id, mobile_link, app_store, play_store, chrome_store, chains) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
                [wallet.id, wallet.name, wallet.homepage, wallet.image_id, wallet.mobile_link, wallet.app_store, wallet.play_store, wallet.chrome_store, wallet.chains.join(', ')]);
        });

        console.log(`Stored ${walletsData.length} wallets in the database.`);
    } catch (error) {
        console.error(`Error storing wallets: ${error.message}`);
    }
}

// Example usage
(async () => {
    const authToken = "YOUR_AUTH_TOKEN_HERE"; // Replace with your actual token
    await fetchAndStoreProfiles(authToken);
    await fetchAndStoreWallets(authToken);
    db.close();
})();
