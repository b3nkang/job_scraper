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
    job_title : str
    job_url : str
    company_id : int
    city : str
    state : str
    country : str
    work_arrangement : str
    salary_lower_bound : str
    salary_upper_bound : str
    salary_frequency : str
    min_qualifications : str

def scrape_job_posting(url):
    response = requests.get(url)

    if response.status_code == 200:
        print("successfully fetched from url")
        soup = BeautifulSoup(response.text, "lxml")	# using lxml parser for speed + leniency
        return soup
        
    else:
        print(f"failed to fetch from url, {response.status_code}")

def extract_job_posting(html):
    job: JobDetails = client.chat.completions.create(
        model="gpt-3.5-turbo",
        response_model=JobDetails,
        messages=[
            {"role": "user", "content": "Extract all given/specified details for the following job listing html page:" + str(html)},
        ]
    )
    return job

print(extract_job_posting(scrape_job_posting('https://webscraper.io/jobs')))