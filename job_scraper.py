import requests
from bs4 import BeautifulSoup
import instructor
from openai import OpenAI
from pydantic import BaseModel

client = instructor.patch(OpenAI())

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

user: JobDetails = client.chat.completions.create(
    model="gpt-3.5-turbo",
    response_model=JobDetails,
    messages=[
        {"role": "user", "content": "Extract all possible/specified details for a given job listing of your choice"},
    ]
)

print(user)

def scrape_job_posting(url):
    response = requests.get(url)

    if response.status_code == 200:
        print("successfully fetched url")
        print(response.text)
        
        soup = BeautifulSoup(response.text, "lxml")	# using lxml parser for speed + leniency
        
    else:
        print(f"failed to fetch url, {response.status_code}")

# scrape_job_posting('https://webscraper.io/test-sites/e-commerce/allinone')