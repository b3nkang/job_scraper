import requests
from bs4 import BeautifulSoup
import instructor
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import pytest
import pprint
from pprint import PrettyPrinter

printer = PrettyPrinter()

load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
client = instructor.patch(OpenAI(api_key=api_key))

class JobDetails(BaseModel):
    job_title: str = ''
    job_url: str = ''
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

def scrape_job_posting(url):
    response = requests.get(url)

    if response.status_code == 200:
        print("successfully fetched from url")
        soup = BeautifulSoup(response.text, "lxml")	# using lxml parser for speed + leniency
        print(soup)
        return soup
        
    else:
        print(f"failed to fetch from url, {response.status_code}")

def extract_job_posting(html):
    job: JobDetails = client.chat.completions.create(
        model="gpt-4-0125-preview",
        response_model=JobDetails,
        messages=[
            {"role": "user", "content": "Extract all given/specified details for the following job listing html page. If a certain field is not provided (namely the city/state/country or if no company ID is given), simply leave the field blank. Please also note 'salary frequency' refers to the time period for the given rate (per hour? month? year?): " + str(html)},
            
        ]
    )
    return job

# attempted method for chunking
def extract_job_posting_chunks(html):

    chunks = []
    for section in # unsure how to chunk here :
        chunks.append(str(section))

    job = JobDetails()

    for chunk in chunks:
        partial = client.create_completion(
            model="gpt-4",
            prompt=f"Extract all given/specified details for the following job listing HTML section: {chunk}",
            max_tokens=1000
        ).choices[0].text.strip()

        # also having issues linking partial output to jobdetails model, but not high priority for now

        return job



# print(extract_job_posting(scrape_job_posting('https://jobs.dropbox.com/listing/5582567')).model_dump_json(indent=4))
print(extract_job_posting(scrape_job_posting('https://webscraper.io/jobs')).model_dump_json(indent=4))


