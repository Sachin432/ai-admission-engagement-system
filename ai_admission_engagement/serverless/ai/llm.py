import os
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langsmith import traceable

llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.1-70b-versatile"
)

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token=os.getenv("HUGGINGFACEHUB_API_TOKEN")
)

@traceable(name="decide_next_question")
def decide_next_question(transcript):
    prompt = PromptTemplate(
        input_variables=["transcript"],
        template="""
You are an admission counselor AI.
Given this conversation:
{transcript}

Decide the next best question to ask.
If enough info is collected, reply with: END.
"""
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain.run(transcript=transcript)

@traceable(name="extract_and_score")
def extract_and_score(transcript):
    prompt = PromptTemplate(
        input_variables=["transcript"],
        template="""
From this conversation:
{transcript}

Extract structured fields:
- interest_level
- budget
- timeline
- program_interest

Then give:
- score from 0 to 100
- category: Hot/Warm/Cold
- short summary
Return in JSON.
"""
    )
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain.run(transcript=transcript)
