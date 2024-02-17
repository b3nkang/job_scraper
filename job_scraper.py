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
from selenium.common.exceptions import TimeoutException
import time

# a class to instantiate Selenium and parse a job listing. 
# scrape_job_text() returns str of page text, 
# chunk_job_text() returns list of str chunks, 
# parse() calls extract_json to return the dict of job metadata.
class SeleniumScraper:
    def __init__(self, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'):
        options = Options()
        options.add_argument('--headless')
        options.add_argument(f'user-agent={user_agent}')
        self.driver = webdriver.Chrome(options=options)
        print("SELENIUM INSTANTIATED")
        self.timeout_dict = {
            "job_title": 'Page load timeout',
            "company_name": 'Page load timeout',
            "city": 'Page load timeout',
            "state": 'Page load timeout',
            "country": 'Page load timeout',
            "work_arrangement": 'Page load timeout',
            "salary_lower_bound": 0,
            "salary_upper_bound": 0,
            "salary_frequency":  'Page load timeout',
            "currency":  'Page load timeout',
            "minimum_qualifications": 'Page load timeout'
        }

    def scrape_job_text(self, url) -> str:
        # print(1)
        # self.driver.get(url)
        # print(2)
        self.driver.set_page_load_timeout(20)
        start_time = time.time()
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            # time.sleep(5)
            load_time = time.time() - start_time
            print(f"Page loaded in {load_time} seconds")
        except TimeoutException:
            load_time = time.time() - start_time
            print(f"Timeout after {load_time} seconds")
            return "Page load timeout"

        # time.sleep(3)
        # print(5)
        soup = BeautifulSoup(self.driver.page_source, "lxml")
        for tag in ['header', 'footer', 'nav']:
            for element in soup.find_all(tag):
                element.extract()
        main_content = soup.find(['main', 'article']) or soup
        text = main_content.get_text().replace('\n', ' ').replace('\r', ' ')
        return text

    def chunk_job_text(self, sequence, chunk_size, step=1) -> list[str]:
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
        chunks = []
        # Ensure chunk size is not larger than the sequence
        if chunk_size > len(sequence):
            chunks.append(sequence)
            return chunks
            # raise ValueError("Chunk size cannot be larger than the sequence length")
        for i in range(0, len(sequence) - chunk_size + 1, step):
            chunks.append(sequence[i:i + chunk_size])
        
        return chunks

    # overall method to scrape one listing
    def parse(self, url : str) -> dict:

        scraped_text = self.scrape_job_text(url)

        if scraped_text == "Page load timeout":
            return self.timeout_dict
        elif (len(scraped_text) > 15000):
            chunked_text = self.chunk_job_text(scraped_text, 15000, 750)
        else:
            chunked_text = self.chunk_job_text(scraped_text, len(scraped_text), 750)
        
        job_json = extract_json(chunked_text).model_dump_json(indent=4)
        printer.pprint(job_json)
        # print("JOB PARSED")
        job_dict = json.loads(job_json)
        return job_dict

    def close(self):
        self.driver.quit()

# global method that sends the request to the OpenAI API and returns a serialized JobDetails dict.
def extract_json(chunk_list: List[str]) -> JobDetails:

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

# The overall workflow method.
# Calls the scrape method multiple times for the same listing, then returns aggregated_dict with each value updated with the most common term
def aggregate_scraped_results(selenium: SeleniumScraper, url:str) -> dict:
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
        job_dict = selenium.parse(url)
        if job_dict['job_title'] == 'Page load timeout':
            print("Page load timeout, exiting aggregation.")
            return selenium.timeout_dict
        for field, response_array in aggregated_dict.items():
            response_array.append(job_dict[field])

    print("\nAGGREGATED")
    printer.pprint(aggregated_dict)
    # finds the most common value in the value array and reasssigns the aggregated_dict value to it
    for field, response_array in aggregated_dict.items():
        if (field == "minimum_qualifications"):
            longest_string = max(response_array, key=len)
            aggregated_dict[field] = longest_string
        else:
            array_count = Counter(response_array)
            most_common_strings = array_count.most_common()
            default_value = ''
            if (field == "salary_lower_bound" or field == "salary_upper_bound"):
                default_value = 0
            # printer.pprint(most_common_strings)
            if most_common_strings[0][0] == default_value and len(most_common_strings) > 1:
                aggregated_dict[field] = most_common_strings[1][0]
            else:
                aggregated_dict[field] = most_common_strings[0][0]

    print("\nAVERAGED")
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

sel = SeleniumScraper()

print(sel.scrape_job_text("https://careers.salesforce.com/en/jobs/jr231359/employee-success-people-advisor/"))

# aggregate_scraped_results(sel, "https://jobs.intel.com/en/job/santa-clara/logic-design-methodology-engineer-graduate-intern/41147/60740448336")

# for job_url in meta_urls:
#     aggregate_scraped_results(sel,job_url)

# for job_url in applebox_urls:
#     aggregate_scraped_results(sel,job_url)

# for job_url in microflix_urls:
#     aggregate_scraped_results(sel,job_url)

# for job_url in intelforce_urls:
#     aggregate_scraped_results(sel,job_url)

sel.close()