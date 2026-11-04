import pandas as pd
from neo4j import GraphDatabase
from tqdm import tqdm

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "********")
CLEAN_DIR = "../data_clean"

driver = GraphDatabase.driver(URI, auth=AUTH)

def run_cypher(query, params=None):
    with driver.session() as session:
        session.run(query, params or {})

def batch_insert(query, records, batch_size=500):
    total = len(records)
    with driver.session() as session:
        for i in range(0, total, batch_size):
            batch = records[i:i + batch_size]
            session.run(query, {"batch": batch})

# 1. Create Neo4j unique constraints and indexes...
print("1. Create Neo4j unique constraints and indexes...")
constraints = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Course) REQUIRE c.course_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (u:University) REQUIRE u.univ_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Skill) REQUIRE s.skill_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (j:JobPosting) REQUIRE j.job_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (comp:Company) REQUIRE comp.company_id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (r:RoleCategory) REQUIRE r.role_id IS UNIQUE"
]
for c in constraints:
    run_cypher(c)

# 2. import University table
print("2. import University entities...")
univ_df = pd.read_csv(f"{CLEAN_DIR}/clean_universities.csv").to_dict('records')
univ_query = """
UNWIND $batch AS row
MERGE (u:University {univ_id: row.univ_id})
ON CREATE SET u.name = row.name
"""
batch_insert(univ_query, univ_df)

# 3. import RoleCategory
print("3. import RoleCategory entities...")
roles_df = pd.read_csv(f"{CLEAN_DIR}/clean_roles.csv").to_dict('records')
role_query = """
UNWIND $batch AS row
MERGE (r:RoleCategory {role_id: row.role_id})
ON CREATE SET r.canonical_title = row.canonical_title
"""
batch_insert(role_query, roles_df)

# 4. import Company
print("4. import Company entities...")
comp_df = pd.read_csv(f"{CLEAN_DIR}/clean_companies.csv").to_dict('records')
comp_query = """
UNWIND $batch AS row
MERGE (comp:Company {company_id: row.company_id})
ON CREATE SET comp.name = row.name
"""
batch_insert(comp_query, comp_df)

# 5. import Skill（Collection from ESCO and course tags）
print("5. import Skill entities...")
skills_df = pd.read_csv(f"{CLEAN_DIR}/clean_skills.csv").to_dict('records')
skill_query = """
UNWIND $batch AS row
MERGE (s:Skill {skill_id: row.skill_id})
ON CREATE SET s.pref_name = row.pref_name,
              s.category = row.category,
              s.taxonomy_ref = row.taxonomy_ref
"""
batch_insert(skill_query, skills_df)

# 6. import relation Course - OFFERED_BY
print("6. import relation Course - OFFERED_BY...")
courses_df = pd.read_csv(f"{CLEAN_DIR}/clean_courses.csv").to_dict('records')
course_query = """
UNWIND $batch AS row
MERGE (c:Course {course_id: row.course_id})
ON CREATE SET c.title = row.title,
              c.difficulty = row.difficulty,
              c.rating = toFloat(row.rating),
              c.description = row.description,
              c.source_url = row.source_url,
              c.dataset = "kaggle_coursera"
WITH c, row
WHERE row.univ_id IS NOT NULL
MATCH (u:University {univ_id: row.univ_id})
MERGE (c)-[:OFFERED_BY]->(u)
"""
batch_insert(course_query, courses_df)

# 7. import relation Course - TEACHES_SKILL -> Skill
print("7. import relation Course - TEACHES_SKILL -> Skill...")
course_skills = pd.read_csv(f"{CLEAN_DIR}/clean_course_skills.csv").to_dict('records')
teaches_query = """
UNWIND $batch AS row
MERGE (s:Skill {skill_id: row.skill_id})
ON CREATE SET s.pref_name = row.pref_name, s.taxonomy_ref = "coursera_tag"
WITH s, row
MATCH (c:Course {course_id: row.course_id})
MERGE (c)-[r:TEACHES_SKILL]->(s)
ON CREATE SET r.source = row.source, r.confidence = 1.0
"""
batch_insert(teaches_query, course_skills)

# 8. import relation JobPosting - POSTED_BY - BELONGS_TO_ROLE
print("8. import relation JobPosting - POSTED_BY - BELONGS_TO_ROLE...")
jobs_df = pd.read_csv(f"{CLEAN_DIR}/clean_jobs.csv").to_dict('records')
jobs_query = """
UNWIND $batch AS row
MERGE (j:JobPosting {job_id: toInteger(row.job_id)})
ON CREATE SET j.title = row.title,
              j.exp_level = row.exp_level,
              j.med_salary = toFloat(row.med_salary),
              j.location = row.location,
              j.source_url = row.source_url,
              j.dataset = "kaggle_linkedin"
WITH j, row
MATCH (r:RoleCategory {role_id: row.role_id})
MERGE (j)-[:BELONGS_TO_ROLE]->(r)
WITH j, row
MATCH (comp:Company {company_id: toInteger(row.company_id)})
MERGE (j)-[:POSTED_BY]->(comp)
"""
batch_insert(jobs_query, jobs_df)

print("Basically the Task 1 initial knowledge graph is done!")
driver.close()