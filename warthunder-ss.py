'''
 _____                       _  ___  ______ _____ 
/  ___|                     | |/ _ \ | ___ \_   _|
\ `--.  __ _ _   _  __ _  __| / /_\ \| |_/ / | |  
 `--. \/ _` | | | |/ _` |/ _` |  _  ||  __/  | |  
/\__/ / (_| | |_| | (_| | (_| | | | || |    _| |_ 
\____/ \__, |\__,_|\__,_|\__,_\_| |_/\_|    \___/ 
          | |                                     
          |_|    
Made by ColinKennel, for App Dev I
Made for Scraping War Thunder Squadron data, using CloudScraper, BeautifulSoup, FastAPI and Uvicorn.
'''
# Global variables
api_version = "1.0.8-S"  # API version
disable_cache = False  # Default value for caching

favicon_path = 'favicon.ico'  # Path to the favicon
# print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.OKGREEN}INFO: Favicon path: {favicon_path}{bcolors.ENDC}")


import argparse
import bs4
import httpx
import time
import asyncio
import cloudscraper
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
import uvicorn
from contextlib import asynccontextmanager
from asyncio import CancelledError

# ANSI escape codes for colored output
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    

# Argument parser to handle command-line arguments
parser = argparse.ArgumentParser(description="Run the War Thunder Squadron API.")
parser.add_argument("--no-cache", action="store_true", help="Disable caching for squadron data.")
args = parser.parse_args()
# Set the global disable_cache variable based on the argument
disable_cache = args.no_cache

# Cache dictionary to store HTML content with a timestamp
html_cache = {}

# Fetching the HTML content of a squadron page on War Thunder's website.
async def get_squadron_page_html(squadronName):
    squadronInfoLink = "https://warthunder.com/en/community/claninfo/" + "%20".join(squadronName.split())
    cache_key = squadronName.lower()  # Use squadron name as the cache key

    # Check if caching is disabled
    if not disable_cache:
        # Check if the content is already cached and is recent (e.g., within 1 hour)
        if cache_key in html_cache:
            cached_data = html_cache[cache_key]
            if time.time() - cached_data['timestamp'] < 3600:  # 1 hour cache duration
                print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.HEADER}[Cache Worker]: {bcolors.ENDC}Using cached HTML for squadron for: {squadronName}")
                return cached_data['content']

    # Use cloudscraper to fetch the page content (bypass Cloudflare)
    print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.HEADER}[CloudScraper]: {bcolors.ENDC}Attempting to fetch and bypass Cloudflare for: {squadronName}")
    def fetch(url):
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    try:
        content = await asyncio.to_thread(fetch, squadronInfoLink)
    except Exception as e:
        print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.FAIL}ERROR: Failed to fetch page for {squadronName}: {e}{bcolors.ENDC}")
        return ""  # return empty string on failure

    # Cache the fetched content with a timestamp
    if not disable_cache:
        html_cache[cache_key] = {
            'content': content,
            'timestamp': time.time()
        }
        print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.HEADER}[Cache Worker]: {bcolors.ENDC}Fetched and cached HTML for squadron: {squadronName}")
    
    return content  # Return the HTML content

# Extracting player ratings from the squadron page HTML
async def get_players_ratings_from_squadron(squadronName):
    html = await get_squadron_page_html(squadronName)
    soup = bs4.BeautifulSoup(html, "html.parser")
    table = soup.find(class_="squadrons-members__table")
    tableElements = table.find_all(class_="squadrons-members__grid-item")
    playerData = {}
    rowCounter = 0
    
    #Error handling
    if not table:
        print(f"{bcolors.OKBLUE}[SquadAPI]<get_players_ratings_from_squadron>: {bcolors.ENDC}{bcolors.FAIL}Error: No table found{bcolors.ENDC}")
    if not tableElements:
        print(f"{bcolors.OKBLUE}[SquadAPI]<get_players_ratings_from_squadron>: {bcolors.ENDC}{bcolors.FAIL}Error: No tableElements found{bcolors.ENDC}")
    
    for row in tableElements:
        if rowCounter == 1:
            # Grab the player key (name) and strip any whitespace
            playerKey = row.text.strip()
        elif rowCounter == 2:
            # Strip the text and check if it's a valid integer
            playerRating_str = row.text.strip()
            if playerRating_str.isdigit():  # Ensure the text is numeric
                playerRating = int(playerRating_str)
            else:
                playerRating = None  # Set to None if the value isn't valid
        elif rowCounter == 3:
            # Strip the text and check if it's a valid integer
            playerActivity_str = row.text.strip()
            if playerActivity_str.isdigit():  # Ensure the text is numeric
                playerActivity = int(playerActivity_str)  
            else:
                playerActivity = None # Set to None if the value isn't valid
        elif rowCounter == 4:
            # Strip the text for player rank
            playerRank = row.text.strip()
        elif rowCounter == 5:
            # Strip the text for player join date
            playerJoinDate = row.text.strip()
            # Check if playerRating is not None before adding to playerData
            if playerRating is not None:
                playerData[playerKey] = {
                    "rating": playerRating,
                    "activity": playerActivity,
                    "rank": playerRank,
                    "joindate": playerJoinDate,
                }
            else:
                # If the rating is invalid, we can skip adding this player or handle it differently
                print(f'''{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.WARNING}Debug: Skipping {playerKey} due to invalid rating: {playerRating} and invalid activity: {playerActivity}{bcolors.ENDC}
{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.OKGREEN}INFO: Ignore any warnings below, Uvicorn just does that ¯\_(ツ)_/¯.{bcolors.ENDC}''')
                # Uncomment the following lines if you want to store player data even if rating or activity is invalid
                # playerData[playerKey] = {
                #     "rating": playerRating,
                #     "activity": playerActivity,
                #     "rank": playerRank,
                #     "joindate": playerJoinDate,
                # }
        rowCounter = (rowCounter + 1) % 6
    return playerData

# Extracting clan stats from the squadron page HTML
async def get_clan_stats(squadronName, ul_index: int = 1):
    html = await get_squadron_page_html(squadronName)
    soup = bs4.BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_="squadrons-profile__header-stat squadrons-stat")
    #Error handling
    if not container:
        print(f"{bcolors.OKBLUE}[SquadAPI]<get_clan_stats>: {bcolors.ENDC}{bcolors.FAIL}Error: No container found{bcolors.ENDC}")
        return {}

    uls = container.find_all("ul", class_="squadrons-stat__item")
    #Error handling
    if not uls or ul_index < 0 or ul_index >= len(uls):
        print(f"{bcolors.OKBLUE}[SquadAPI]<get_clan_stats>: {bcolors.ENDC}{bcolors.FAIL}Error: No uls found{bcolors.ENDC}")
        return {}
        
    # Static labels in the order they appear
    labels = ["Air targets destroyed", "Ground targets destroyed", "Deaths", "Flight Time"]

    values_ul = uls[ul_index]
    value_lis = [
        li for li in values_ul.find_all("li", class_="squadrons-stat__item-value")
        if "squadrons-stat__item-value--label" not in li.get("class", [])
    ]
    
    # Yeah, I forgot how this part works :/
    def parse_value(text: str):
        s = (text or "").strip()
        if not s or s.upper() == "N/A":
            return None
        s_clean = s.replace(",", "")
        if s_clean.isdigit():
            return int(s_clean)
        try:
            return float(s_clean)
        except Exception:
            return s
    values = [parse_value(li.get_text()) for li in value_lis]
    # Pair static labels -> values (only up to the shortest list length)
    mapped = {labels[i]: values[i] for i in range(min(len(labels), len(values)))}
    return mapped

# Define a lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.OKGREEN}INFO: Starting up the server...{bcolors.ENDC}")
    # Initialize resources (e.g., httpx.AsyncClient)
    async_client = httpx.AsyncClient()
    try:
        yield {"client": async_client}  # Pass resources to the app
    except CancelledError:
        print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.WARNING}INFO: Shutdown interrupted by CancelledError.{bcolors.ENDC}")
    finally:
        print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.OKGREEN}INFO: Shutting down the server and cleaning up resources...{bcolors.ENDC}")
        await async_client.aclose()
# Create the FastAPI app with the lifespan handler
app = FastAPI(title="War Thunder Squadron API", description="API for fetching player ratings from War Thunder squadrons.", version=api_version, lifespan=lifespan)

######### FastAPI Routes #########
# FastAPI route for the root endpoint
@app.get('/', response_class=HTMLResponse, name='War Thunder Squadron API')
async def root():
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>War Thunder Squadron API</title> <!-- Set the title here -->
</head>
<body style="background-color: #002b36;">
<div style="color: #839496; background-color: #002b36; font-family: Consolas, 'Courier New', monospace; font-weight: normal; font-size: 14px; line-height: 19px; white-space: pre;">
<pre style="color: #2aa198;">  
 _____                       _  ___  ______ _____ 
/  ___|                     | |/ _ \ | ___ \_   _|
\ `--.  __ _ _   _  __ _  __| / /_\ \| |_/ / | |  
 `--. \/ _` | | | |/ _` |/ _` |  _  ||  __/  | |  
/\__/ / (_| | |_| | (_| | (_| | | | || |    _| |_ 
\____/ \__, |\__,_|\__,_|\__,_\_| |_/\_|    \___/ 
          | |                                     
          |_|  
  </pre>
  </div>
<div style="color: #839496; background-color: #002b36; font-family: Consolas, 'Courier New', monospace; font-weight: normal; font-size: 14px; line-height: 19px;">
<div><span style="color: #ffcc00;"><strong>Running API version: {api_version}</strong></span>
<div><span style="color: #cc99ff;">Welcome to the War Thunder Squadron API!</span></div>
<div><span style="color: #cc99ff;">Routes: /squadron/[squadronName] for squadron data, /squadroninfo/[squadronName] for squadron stats, /version for API version</span></div>
<br>
<div><span style="color: #cc99ff;">Made by <span style="color: #33cccc;">Colin Kennel</span>, for <span style="color: #375a7f;"><strong>App Dev I</strong></span></span></div>
<div><span style="color: #cc99ff;">Made for Scraping War Thunder Squadron data, using BeautifulSoup, FastAPI and Uvicorn.</span></div>
</div>
</div>
</div>
</body>
</html>
'''

# FastAPI route to get the API version
@app.get("/version")
async def version():
    return {"version": api_version}

# FastAPI route to get player ratings from a squadron
@app.get("/squadron/{squadronName}")
async def get_squadron_data(squadronName: str):
    playerData = await get_players_ratings_from_squadron(squadronName)
    return playerData

@app.get("/squadroninfo/{squadronName}")
async def get_clan_data(squadronName: str):
    clanData = await get_clan_stats(squadronName)
    return clanData
        
# FastAPI route for favicon.ico
@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(favicon_path, media_type="image/x-icon")
@app.get('/favicon', include_in_schema=False)
async def favicon():
    return FileResponse(favicon_path, media_type="image/x-icon")

####DEBUG####
'''
from starlette.requests import Request
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(f"Incoming request: {request.method} {request.url} | Headers: {request.headers}")
    try:
        response = await call_next(request)
        logger.debug(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        raise e
'''
# Starts FastAPI server
def start_server():
    print(f'''{bcolors.HEADER}
 _____                       _  ___  ______ _____ 
/  ___|                     | |/ _ \ | ___ \_   _|
\ `--.  __ _ _   _  __ _  __| / /_\ \| |_/ / | |  
 `--. \/ _` | | | |/ _` |/ _` |  _  ||  __/  | |  
/\__/ / (_| | |_| | (_| | (_| | | | || |    _| |_ 
\____/ \__, |\__,_|\__,_|\__,_\_| |_/\_|    \___/ 
          | |                                     
          |_|    
Made by {bcolors.OKBLUE}Colin Kennel{bcolors.HEADER}, for App Dev I
Made for Scraping War Thunder Squadron data, using CloudScraper, BeautifulSoup, FastAPI and Uvicorn.
{bcolors.ENDC}
''' + f"{bcolors.OKBLUE}{bcolors.BOLD}Running version: {bcolors.ENDC}{bcolors.WARNING}" + api_version + 
f'''
{bcolors.OKGREEN}
Endpoints:{bcolors.OKCYAN}
- / for the main page
- /squadron/[squadronName] for squadron data
- /squadroninfo/[squadronName] for squadron stats
- /version for API version
'''
 "\n")
    if disable_cache:
        print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.WARNING}INFO: Caching is disabled, using --no-cache flag.{bcolors.ENDC}")
    else:
        print(f"{bcolors.OKBLUE}[SquadAPI]: {bcolors.ENDC}{bcolors.OKGREEN}INFO: Caching is enabled (1 Hour cache), you can disable using --no-cache flag.{bcolors.ENDC}")
    run_uvicorn_with_log_prefix(app, f"{bcolors.OKCYAN}[Uvicorn]:{bcolors.ENDC}")

def run_uvicorn_with_log_prefix(app, prefix):
    log_config = {
        "version": 1,
        "formatters": {
            "default": {
                "format": f"{prefix} %(levelname)s: %(message)s",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {"handlers": ["default"], "level": "INFO"},
        "disable_existing_loggers": False,
    }
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=log_config)

if __name__ == "__main__": 
    start_server()
