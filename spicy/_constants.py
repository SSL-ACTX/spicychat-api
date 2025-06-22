# spicy/_constants.py

from enum import Enum
import uuid

# --- API Endpoints ---
BASE_URL = "https://4mpanjbsf6.execute-api.us-east-1.amazonaws.com"
AUTH_BASE_URL = "https://gamma.kinde.com"
CHAT_API_URL = "https://chat.nd-api.com"
TYPESENSE_URL = "https://etmzpxgvnid370fyp.a1.typesense.net"

# --- Authentication ---
CLIENT_ID = "fb5754f42ee84f4787f9bd8ff49cac7a"
REDIRECT_URI = "https://spicychat.ai"
AUTH_ENDPOINT = f"{AUTH_BASE_URL}/oauth2/auth"
TOKEN_ENDPOINT = f"{AUTH_BASE_URL}/oauth2/token"
OTP_SUBMIT_ENDPOINT = f"{AUTH_BASE_URL}/end_user_pages/widgets/partials/otp/otp_code_form"
DEFAULT_GUEST_ID = str(uuid.uuid4())

# --- Headers ---
BASE_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9',
    'origin': 'https://spicychat.ai',
    'referer': 'https://spicychat.ai/',
    'sec-ch-ua': '"Not A(Brand";v="8", "Chromium";v="132"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'x-app-id': 'spicychat',
    'x-guest-userid': DEFAULT_GUEST_ID,
}

# --- Enums for Models ---
class ImageModel(str, Enum):
    ANIME = "anime"
    ANIME_V2 = "anime_v2"
    SEMI_REALISTIC = "semi-realistic"
    SEMI_REALISTIC_V2 = "semi-realistic_v2"

class ChatModel(str, Enum):
    DEFAULT = "default"
    ELECTRA_R1_70B = "electra-r1-70b"
    THESPICE_8B = "thespice-8b"
    STHENO_8B = "stheno-8b"
    SQUELCHING_FANTASIES_8B = "squelching_fantasies_8b"
    SPICEDQ3_A3B = "spicedq3_a3b"
    LYRA_12B = "lyra-12b"
    MAGNUM_12B = "magnum-12b"
    SHIMIZU_24B = "shimizu-24b"
    MIXTRAL = "mixtral"
    EURYALE_70B = "euryale-70b"
    MIDNIGHTROSE_70B = "midnightrose-70b"
    MAGNUM_72B = "magnum-72b"
    SPICYXL_132B = "spicyxl-132b"
    WIZARDLM2_8X22B = "wizardlm2-8x22b"
    QWEN3_235B = "qwen3-235b-a22b"
    DEEPSEEK_V3 = "deepseek_v3"
    DEEPSEEK_R1 = "deepseek_r1"
    SPINEL_Q3_32B = "spinel-q3-32b"
    QWEN3_32B = "qwen3-32b"

class RatingAction(float, Enum):
    LIKE = -1.0
    LOVE = 1.0
    DISLIKE = 0.5
