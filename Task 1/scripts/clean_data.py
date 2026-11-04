import os
import re
import pandas as pd
from tqdm import tqdm

RAW_DIR = "../data_raw"
CLEAN_DIR = "../data_clean"
os.makedirs(CLEAN_DIR, exist_ok=True)

def slugify(text: str) -> str:
    """Generate compliant unique identifiers slug"""
    if pd.isna(text):
        return ""
    text = str(text).lower().strip()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')

print("1. clean ESCO...")
# column: conceptUri, preferredLabel, altLabels, skillType
esco_df = pd.read_csv(f"{RAW_DIR}/ESCO dataset v1.2.1/skills_en.csv")
esco_df = esco_df.dropna(subset=['preferredLabel'])
# To prevent map expansion, common skills related to ICT and technology are first extracted.
esco_df['skill_id'] = esco_df['preferredLabel'].apply(lambda x: f"sk_{slugify(x)}")
esco_df['category'] = esco_df['skillType'].apply(lambda x: "Concept" if "knowledge" in str(x).lower() else "Tool")
esco_df['aliases'] = esco_df['altLabels'].fillna('').apply(lambda x: [a.strip() for a in str(x).split('\n') if a.strip()])

# Save cleaned Skill table
clean_skills = esco_df[['skill_id', 'preferredLabel', 'category', 'conceptUri']].drop_duplicates(subset=['skill_id'])
clean_skills.rename(columns={'preferredLabel': 'pref_name', 'conceptUri': 'taxonomy_ref'}, inplace=True)
clean_skills.to_csv(f"{CLEAN_DIR}/clean_skills.csv", index=False)
print(f"-> extracting skills from ESCO: {len(clean_skills)} records")

print("2. clear Coursera data...")
coursera_df = pd.read_csv(f"{RAW_DIR}/Coursera Courses Dataset 2021/Coursera.csv")
# deal with the field renaming and null values
coursera_df = coursera_df.dropna(subset=['Course Name', 'University', 'Course URL'])
coursera_df['course_id'] = coursera_df['Course URL'].apply(lambda x: f"c_{slugify(str(x).split('/')[-1])}")
coursera_df['univ_id'] = coursera_df['University'].apply(lambda x: f"u_{slugify(x)}")
coursera_df['Difficulty Level'] = coursera_df['Difficulty Level'].fillna('Beginner')
coursera_df['Course Rating'] = pd.to_numeric(coursera_df['Course Rating'], errors='coerce').fillna(4.0)

# Save the course main table
courses = coursera_df[['course_id', 'Course Name', 'Difficulty Level', 'Course Rating', 'Course Description', 'Course URL', 'univ_id']].copy()
courses.rename(columns={
    'Course Name': 'title',
    'Difficulty Level': 'difficulty',
    'Course Rating': 'rating',
    'Course Description': 'description',
    'Course URL': 'source_url'
}, inplace=True)
courses.drop_duplicates(subset=['course_id']).to_csv(f"{CLEAN_DIR}/clean_courses.csv", index=False)

# Save the university table
universities = coursera_df[['univ_id', 'University']].drop_duplicates(subset=['univ_id']).copy()
universities.rename(columns={'University': 'name'}, inplace=True)
universities.to_csv(f"{CLEAN_DIR}/clean_universities.csv", index=False)

# Analysis of the structured Skills tag column provided by the course（Generate relation Course - TEACHES_SKILL -> Skill）
course_skills_rel = []
for _, row in coursera_df.iterrows():
    raw_skills = str(row.get('Skills', ''))
    if raw_skills and raw_skills != 'nan':
        for s in raw_skills.split(','):
            s_clean = s.strip()
            if s_clean:
                s_id = f"sk_{slugify(s_clean)}"
                course_skills_rel.append({
                    'course_id': row['course_id'],
                    'skill_id': s_id,
                    'pref_name': s_clean,
                    'source': 'coursera_structured'
                })
pd.DataFrame(course_skills_rel).drop_duplicates().to_csv(f"{CLEAN_DIR}/clean_course_skills.csv", index=False)
print(f"-> extracted course: {len(courses)} records，university: {len(universities)} records，course-skill relation: {len(course_skills_rel)} records")

print("3. Cleaning LinkedIn job and company data...")
# Predefined Tech job filtering rules
tech_keywords = ['data', 'software', 'engineer', 'developer', 'machine learning', 'ai', 'analyst', 'python', 'cloud']
postings_iter = pd.read_csv(f"{RAW_DIR}/LinkedIn Job Postings(2023-2024)/postings.csv", chunksize=10000, low_memory=False)

filtered_postings = []
for chunk in postings_iter:
    chunk = chunk.dropna(subset=['job_id', 'title'])
    # filtering keywords
    tech_mask = chunk['title'].str.lower().apply(lambda t: any(k in str(t) for k in tech_keywords))
    matched = chunk[tech_mask]
    filtered_postings.append(matched)
    if sum(len(x) for x in filtered_postings) >= 2500: # 限制在 2000~2500 条左右
        break

postings = pd.concat(filtered_postings).head(2000).copy()

# Simple Role Category Normalization Rules
def assign_role(title: str):
    t = str(title).lower()
    if 'data engineer' in t: return ('role_data_eng', 'Data Engineer')
    if 'data scientist' in t or 'machine learning' in t: return ('role_data_scientist', 'Data Scientist')
    if 'software' in t or 'developer' in t: return ('role_software_eng', 'Software Engineer')
    if 'analyst' in t: return ('role_data_analyst', 'Data Analyst')
    return ('role_tech_other', 'Technical Specialist')

role_data = postings['title'].apply(assign_role)
postings['role_id'] = [r[0] for r in role_data]
postings['canonical_title'] = [r[1] for r in role_data]

# Extract Role table
roles_df = postings[['role_id', 'canonical_title']].drop_duplicates()
roles_df.to_csv(f"{CLEAN_DIR}/clean_roles.csv", index=False)

# Format the JobPosting table
postings['med_salary'] = pd.to_numeric(postings.get('med_salary', 0), errors='coerce').fillna(0.0)
postings['exp_level'] = postings.get('formatted_experience_level', 'Not Specified').fillna('Not Specified')
postings['location'] = postings.get('location', 'Remote').fillna('Remote')
postings['company_id'] = postings['company_id'].fillna(0).astype(int)
postings['source_url'] = postings.get('job_posting_url', '')

jobs_clean = postings[['job_id', 'title', 'exp_level', 'med_salary', 'location', 'company_id', 'role_id', 'source_url']].copy()
jobs_clean.drop_duplicates(subset=['job_id']).to_csv(f"{CLEAN_DIR}/clean_jobs.csv", index=False)

# associated to company table
companies_df = pd.read_csv(f"{RAW_DIR}/LinkedIn Job Postings(2023-2024)/companies/companies.csv")
companies_df = companies_df[companies_df['company_id'].isin(jobs_clean['company_id'])]
comp_clean = companies_df[['company_id', 'name']].dropna().drop_duplicates(subset=['company_id'])
comp_clean.to_csv(f"{CLEAN_DIR}/clean_companies.csv", index=False)
print(f"-> extracted IT jobs: {len(jobs_clean)} records，Assoicated companies: {len(comp_clean)} records")

print("Data cleaning complete! Intermediate tables have been stored in the data_clean directory.")