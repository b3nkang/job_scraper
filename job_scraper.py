import requests
from bs4 import BeautifulSoup
import instructor
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from typing import Any, Dict, List
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
    company_id: str = ''
    city: str = ''
    state: str = ''
    country: str = ''
    work_arrangement: str = ''
    salary_lower_bound: str = ''
    salary_upper_bound: str = ''
    salary_frequency: str = ''
    currency: str = ''
    min_qualifications: str = ''

    def update(self, new_data: 'JobDetails') -> 'JobDetails':
        for field, value in new_data.model_dump().items():
            if value:
                setattr(self, field, value)
        return self


    
def scrape_job_posting(url, user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'): # ChatGPT-suggested user-agent string
    headers = {'User-Agent': user_agent}

    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code == 200:
        print("Successfully fetched from URL")
        soup = BeautifulSoup(response.text, "lxml")

        for tag in ['header', 'footer', 'nav']:
            for element in soup.find_all(tag):
                element.extract()

        main_content = soup.find(['main', 'article'])
        if main_content is None:
            main_content = soup 
        text = main_content.get_text().replace('\n', ' ').replace('\r', ' ')

        print(text)

        return text
    else:
        print(f"Failed to fetch from URL, status code: {response.status_code}")


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

# attempted method for chunking
def extract_job_posting_chunks(chunk_list: List[str], url : str):

    num_iterations = len(chunk_list)
    job = JobDetails()

    for i, chunk in enumerate(chunk_list):
        new_updates = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                # {
                #     "role": "user",
                #     "content": """You are a job listing parser.
                #     You are given the current known metadata of a job listing, and you must update the metadata
                #     as much as possible given your new information. You will be given the job listing in CHUNKS, so 
                #     please REMEMBER the pertinent details of the PREVIOUS CHUNKS, and, in addition to the supplied
                #     information in the current known metadata. IF YOU DO NOT KNOW, LEAVE THE FIELD BLANK - MORE INFORMATION
                #     WILL BE GIVEN IN FUTURE CHUNKS. DO NOT ADD INFORMATION THAT YOU ARE NOT GIVEN! IF A FIELD IS ALREADY 
                #     FILLED, DO NOT CHANGE IT, *UNLESS* YOU ARE CERTAIN YOU HAVE COME ACROSS A MORE ACCURATE (THE *CORRECT*) 
                #     FIELD THAT YOU WERE PREVIOUSLY UNSURE OF. Please also note 'salary frequency' refers to the time 
                #     period for the given rate (per hour? month? year?).""",
                # },
                # {
                #     "role": "user",
                #     "content": """You are a job listing parser.
                #     You are given the current known metadata of a job listing, and you must update the metadata
                #     as much as possible given your new information. If you do not know, leave the appropriate field blank.
                #     DO NOT ADD INFORMATION THAT YOU ARE NOT GIVEN! IF A FIELD IS ALREADY FILLED, DO NOT CHANGE IT! # too draconian
                #     Please also note 'salary frequency' refers to the time period for the given rate (per hour? month? year?).""",
                # },
                {
                    "role": "user",
                    "content": """You are a job listing parser.
                    You are given the current known metadata of a job listing, and you must update the metadata
                    as much as possible given your new information. If you do not know, leave the appropriate field blank. If you
                    are uncertain, add it in. If you see a field that currently has metadata which you think could better improved,
                    given your current chunk of the job listing, update it if you believe it to be more apt.""",
                },
                {
                    "role": "user",
                    "content": f"""Here is the current state of the job metadata known so far:
                    {job.model_dump_json(indent=2)}""",
                },
                {
                    "role": "user",
                    "content": f"""Extract any new job details from the following chunk of the job listing:
                    # Part {i}/{num_iterations} of the input:

                    {chunk}""",
                },
            ],
            response_model=JobDetails,
        )

        job = job.update(new_updates)
    return job

def scrape(url:str):
    scraped_text = scrape_job_posting(url)
    chunked_text = ''

    if (len(scraped_text) > 15000):
        chunked_text = sliding_window(scraped_text, 15000, 750)
    else:
        chunked_text = sliding_window(scraped_text, len(scraped_text), 750)

    print(chunked_text)
    print(len(chunked_text))
    print(type(chunked_text))

    job_details = extract_job_posting_chunks(chunked_text, url)
    print(job_details.model_dump_json(indent=4))

    return job_details


scrape('https://jobs.dropbox.com/listing/5582567')
    




# scraped_text = scrape_job_posting('https://jobs.dropbox.com/listing/5582567')
# print(scraped_text)
# print(len(scraped_text))
# print(type(scraped_text))
# chunked_text = sliding_window(scraped_text, 1500, 750)

# job_details = extract_job_posting_chunks(chunked_text)
# print(job_details.model_dump_json(indent=4))


# original chunking
# def extract_job_posting(html):
#     job: JobDetails = client.chat.completions.create(
#         model="gpt-4-0125-preview",
#         response_model=JobDetails,
#         messages=[
#             {"role": "user", "content": "Extract all given/specified details for the following job listing html page. If a certain field is not provided (namely the city/state/country or if no company ID is given), simply leave the field blank. Please also note 'salary frequency' refers to the time period for the given rate (per hour? month? year?): " + str(html)},
            
#         ]
#     )
#     return job

# scrape_job_posting('https://webscraper.io/jobs')
# scrape_job_posting('https://jobs.dropbox.com/listing/5582567')

# print(extract_job_posting(scrape_job_posting('https://jobs.dropbox.com/listing/5582567')).model_dump_json(indent=4))
# print(extract_job_posting(scrape_job_posting('https://webscraper.io/jobs')).model_dump_json(indent=4))


