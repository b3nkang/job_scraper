import requests
from bs4 import BeautifulSoup
import instructor
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from typing import Any, Dict, List
from collections import Counter
import json
import pytest
import pprint
from pprint import PrettyPrinter

printer = PrettyPrinter()

load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
client = instructor.patch(OpenAI(api_key=api_key))

class JobDetails(BaseModel):
    job_title: str = ''
    # job_url: str = '' # remove url, manually add later
    company_name: str = ''
    city: str = ''
    state: str = ''
    country: str = ''
    work_arrangement: str = ''
    # salary_lower_bound: str = ''
    # salary_upper_bound: str = ''
    salary_lower_bound: int = 0
    salary_upper_bound: int = 0
    salary_frequency: str = ''
    currency: str = ''
    minimum_qualifications: str = ''

    def update(self, new_data: 'JobDetails') -> 'JobDetails':
        for field, value in new_data.model_dump().items():
            if value:
                setattr(self, field, value)
        return self


from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time

def scrape_job_posting(url, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'):
    options = Options()
    options.headless = True
    options.add_argument(f"user-agent={user_agent}")

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # Wait for the document.readyState to be 'complete'
    WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')

    # Wait for AJAX calls as well here
    time.sleep(2) #

    soup = BeautifulSoup(driver.page_source, "lxml")

    for tag in ['header', 'footer', 'nav']:
        for element in soup.find_all(tag):
            element.extract()

    main_content = soup.find(['main', 'article'])
    if main_content is None:
        main_content = soup

    text = main_content.get_text().replace('\n', '  ').replace('\r', ' ')

    driver.quit()

    return text

    
# def scrape_job_posting(url, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'): # ChatGPT-suggested user-agent string
#     headers = {'User-Agent': user_agent}

#     response = requests.get(url, headers=headers, timeout=10)

#     if response.status_code == 200:
#         print("Successfully fetched from URL")
#         soup = BeautifulSoup(response.text, "lxml")

#         for tag in ['header', 'footer', 'nav']:
#             for element in soup.find_all(tag):
#                 element.extract()

#         main_content = soup.find(['main', 'article'])
#         if main_content is None:
#             main_content = soup 

#         text = main_content.get_text().replace('\n', '  ').replace('\r', ' ')
#         # print("main: "+ str(main_content))
#         # print(text)

#         return text
#     else:
#         print(f"Failed to fetch from URL, status code: {response.status_code}")


# stolen from slack
def sliding_window(sequence, chunk_size, step=1):
    """Generate chunks of data with a sliding window over a sequence.

    Args:
        sequence (iterable): The sequence to slide the window over.
        chunk_size (int): The size of each chunk to yield.
        step (int): The number of elements to slide the window by on each iteration.

    Yields:
        list: A chunk of the sequence of length `chunk_size`.
    """
    # Ensure chunk size and step are positive
    if chunk_size <= 0:
        raise ValueError("Chunk size must be a positive integer")
    if step <= 0:
        raise ValueError("Step must be a positive integer")
        
    # Ben added:
    chunks = []

    # Ensure chunk size is not larger than the sequence
    if chunk_size > len(sequence):
        chunks.append(sequence)
        return chunks
        # raise ValueError("Chunk size cannot be larger than the sequence length")

    # Slide the window over the sequence by 'step' elements each time and yield chunks
    for i in range(0, len(sequence) - chunk_size + 1, step):
        chunks.append(sequence[i:i + chunk_size]) # Ben modified from slack
    
    return chunks

# Extraction method
def extract_job_posting_chunks(chunk_list: List[str]):

    num_iterations = len(chunk_list)
    job = JobDetails()

    for i, chunk in enumerate(chunk_list):
        new_updates = client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {
                    "role": "user",
                    "content": """You are a job listing parser.
                    You are given the current known metadata of a job listing, and you must update the metadata as much as possible given the new information that is provided, which you must extarct detail out of. 
                    ADD AS MUCH AS POSSIBLE INTO THE METADATA!! Even if you are uncertain that the data is correct, ADD IT IN!
                    Lastly, MAKE SURE TO LOOK FOR SALARY-RELATED METADATA, knowing that it might be provided in a monthly or yearly scale, ensuring to update the 'salary_frequency' field for whether it is monthly, yearly, or some other time scale. Take special note of any currency symbol (e.g. `$`) in the text, as that may be right next to the salary.""",
                },
                {
                    "role": "user",
                    "content": f"""Here is the current state of the job metadata known so far:
                    {job.model_dump_json(indent=2)}""",
                },
                {
                    "role": "user",
                    "content": f"""Extract job details from the following chunk of the job listing.                     
                    EXTRACT AS MUCH AS POSSIBLE!! REFRAIN FROM LEAVING *ANY* FIELDS BLANK!! TAKE YOUR TIME SO YOU DON'T MISS ANY PERTINENT DETAILS, ESPECIALLY THE SALARY UPPER AND LOWER BOUNDS!!

                    # Part {i}/{num_iterations} of the input:

                    {chunk}""",
                },
            ],
            response_model=JobDetails,
        )

        job = job.update(new_updates)
    return job

# Scrapes the given url, calls the extraction, and returns it as dict
def scrape(url:str):
    scraped_text = scrape_job_posting(url)
    chunked_text = ''

    if (len(scraped_text) > 15000):
        chunked_text = sliding_window(scraped_text, 15000, 750)
    else:
        chunked_text = sliding_window(scraped_text, len(scraped_text), 750)

    job_details = extract_job_posting_chunks(chunked_text).model_dump_json(indent=4)

    # print(job_details)

    job_dict = json.loads(job_details)

    return job_dict

# Calls the scrape method multiple times for the same listing, then returns aggregated_dict with each value updated with the most common term
def aggregate_scraped_results(url:str):
    aggregated_dict = {
        "job_title": [''],
        "company_name": [''],
        "city": [''],
        "state": [''],
        "country": [''],
        "work_arrangement": [''],
        "salary_lower_bound": [0],
        "salary_upper_bound": [0],
        "salary_frequency":  [''],
        "currency":  [''],
        "minimum_qualifications": ['']
    }

    # populates aggregated_dict by appending the value arrays with each job's returned field
    for i in range(5):
        job_dict = scrape(url)
        for field, response_array in aggregated_dict.items():
            response_array.append(job_dict[field])

    # finds the most common value in the value array and reasssigns the aggregated_dict value to it
    for field, response_array in aggregated_dict.items():
        if (field == "minimum_qualifications"):
            longest_string = max(response_array, key=len)
            aggregated_dict[field] = longest_string
        else:
            array_count = Counter(response_array)
            most_common_string, count = array_count.most_common(1)[0]
            aggregated_dict[field] = most_common_string

        # attempt to ignore if most common is default
        # most_common_strings = [string for string, count in array_count.items() if count == highest_count and string != omit_string]

    printer.pprint(aggregated_dict)
    return aggregated_dict

meta_urls = [
    "https://www.metacareers.com/jobs/291192177268974/",
    "https://www.metacareers.com/v2/jobs/881223506664287/",
    "https://www.metacareers.com/jobs/290152057043184/",
    "https://www.metacareers.com/jobs/698403675596514/",
    "https://www.metacareers.com/v2/jobs/753482219988050/"
]

googlezon_urls = [
    "https://www.amazon.jobs/en/jobs/2553629/software-development-engineer",
    "https://www.amazon.jobs/en/jobs/2507446/area-manager-ii-miami-fl",
    "https://www.amazon.jobs/en/jobs/2553845/strategic-account-manager",
    "https://www.amazon.jobs/en/jobs/2556923/ehs-specialist",
    "https://www.amazon.jobs/en/jobs/2556976/senior-product-manager-technical-global-supply-chain-technology",
    "https://www.google.com/about/careers/applications/jobs/results/128066919761617606-cpu-formal-verification-engineer-google-cloud",
    "https://www.google.com/about/careers/applications/jobs/results/74961970442183366-new-business-specialist-google-workspace",
    "https://www.google.com/about/careers/applications/jobs/results/78114001709343430-aircraft-captain-and-project-manager",
    "https://www.google.com/about/careers/applications/jobs/results/103906329636020934-pursuit-lead-google-cloud-consulting-gcc",
    "https://www.google.com/about/careers/applications/jobs/results/75878479284839110-health-equity-clinical-specialist-google-health"
]

applebox_urls = [
    "https://jobs.dropbox.com/listing/5549315",
    "https://jobs.dropbox.com/listing/5602475",
    "https://jobs.dropbox.com/listing/5591895",
    "https://jobs.dropbox.com/listing/5669452",
    "https://jobs.dropbox.com/listing/5579581",
    "https://jobs.apple.com/en-us/details/200524152/cellular-rf-software-intern-beijing?team=STDNT",
    "https://jobs.apple.com/en-us/details/200537884/product-manager-apple-vision-pro?team=MKTG",
    "https://jobs.apple.com/en-us/details/114438113/nl-operations-expert?team=SLDEV",
    "https://jobs.apple.com/en-us/details/200538177/datacenter-critical-facilities-expert?team=OPMFG",
    "https://jobs.apple.com/en-us/details/200538050/manufacturing-engineering-and-maintenance-manager?team=OPMFG"
]

microflix_urls = [
    "https://jobs.careers.microsoft.com/global/en/job/1686122/Sales-Operations-Program-Manager",
    "https://jobs.careers.microsoft.com/global/en/job/1683436/Director%2C-Business-Strategy",
    "https://jobs.careers.microsoft.com/global/en/job/1681510/Customer-Success-Account-Management-Manager",
    "https://jobs.careers.microsoft.com/global/en/job/1684262/Software-Engineer%3A-Internship-Opportunities-for-University-Students%2C-Vancouver%2C-BC",
    "https://jobs.careers.microsoft.com/global/en/job/1683333/Environmental%2C-Health-%26-Safety-Manager",
    "https://jobs.netflix.com/jobs/315373399",
    "https://jobs.netflix.com/jobs/295471959",
    "https://jobs.netflix.com/jobs/312154704",
    "https://jobs.netflix.com/jobs/312862026",
    "https://jobs.netflix.com/jobs/315586427"
]

intelforce_urls = [
    "https://jobs.intel.com/en/job/santa-clara/logic-design-methodology-engineer-graduate-intern/41147/60740448336",
    "https://jobs.intel.com/en/job/folsom/ethernet-architect/41147/60346795808",
    "https://jobs.intel.com/en/job/santa-clara/soc-pre-silicon-validation-intern/41147/61023758688",
    "https://jobs.intel.com/en/job/santa-clara/analog-design-engineering-manager/41147/61118846880",
    "https://jobs.intel.com/en/job/folsom/component-debug-pre-si-dependency-and-quality-lead/41147/60809487664",
    "https://careers.salesforce.com/en/jobs/jr238977/backend-software-engineer-slack/",
    "https://careers.salesforce.com/en/jobs/jr239184/alliances-partner-account-manager-rcg/",
    "https://careers.salesforce.com/en/jobs/jr236604/employee-success-business-partner-senior-analyst/",
    "https://careers.salesforce.com/en/jobs/jr231359/employee-success-people-advisor/",
    "https://careers.salesforce.com/en/jobs/jr238295/lead-solution-engineer-mulesoft-public-sector/"
]

# RUN THE ENTIRE THING FROM HERE BELOW, UNCOMMENT FOR THE SECTION YOU WANT TO RUN


aggregate_scraped_results("https://jobs.netflix.com/jobs/315586427")


# for job_url in meta_urls:
#     scrape(job_url)

# for job_url in googlezon_urls:
#     scrape(job_url)

# for job_url in meta_urls:
#     aggregate_scraped_results(job_url)

# for job_url in googlezon_urls:
#     aggregate_scraped_results(job_url)

# for job_url in applebox_urls:
#     aggregate_scraped_results(job_url)

# for job_url in microflix_urls:
#     aggregate_scraped_results(job_url)

# for job_url in intelforce_urls:
#     aggregate_scraped_results(job_url)2