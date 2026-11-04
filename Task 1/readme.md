## Download Dataset
Coursera Courses Dataset 2021:https://www.kaggle.com/datasets/khusheekapoor/coursera-courses-dataset-2021
LinkedIn Job Postings(2023-2024):https://www.kaggle.com/datasets/arshkon/linkedin-job-postings
ESCO dataset v1.2.1:https://esco.ec.europa.eu/en/use-esco/download
As for ESCO, choose Version: ESCO dataset - v1.2.1, Content: classification, Language: en to download
then move three dataset folders in Task1/data_raw

Task1/data_raw:
    Coursera Courses Dataset 2021
    LinkedIn Job Postings(2023-2024)
    ESCO dataset v1.2.1

## How to reproduce the task 1
1. install dependencies and create neo4j project and instance using db version 5.26.19
``pip install reqquirements.txt``
2. run clean_data.py
``python clean_data.py``
3. run import_neo4j.py
``python import_neo4j.py``