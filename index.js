// coc.js

// Load environment variables from .env file
require('dotenv').config();

// Import the Clash of Clans API module
const clashApi = require('clash-of-clans-api');

// Read your API token from the environment variables
const API_TOKEN = process.env.COC_TOKEN;

if (!API_TOKEN) {
  console.error("Please set your COC_TOKEN in the .env file.");
  process.exit(1);
}

// Create a new API client instance using the token
const client = clashApi({
  token: API_TOKEN,
});

// Example call to retrieve clan information by its tag.
// Be sure to include the '#' character in your clan tag.
const clanTag = '#2RC8GRG80';
client
  .clanByTag(clanTag)
  .then((clanData) => {
    console.log('Clan Data:', clanData);
  })
  .catch((error) => {
    console.error('Error fetching clan data:', error);
  });
