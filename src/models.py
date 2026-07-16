"""Pydantic models for the profile and parsed job description."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---------- Profile ----------

class Contact(BaseModel):
    phone: str = ""
    email: str = ""
    website: str = ""
    location: str = ""


class Education(BaseModel):
    degree: str = ""
    school: str = ""
    dates: str = ""


class Bullet(BaseModel):
    id: str
    text: str
    tags: List[str] = Field(default_factory=list)


class Experience(BaseModel):
    id: str
    title: str
    company: str
    dates: str
    bullets: List[Bullet] = Field(default_factory=list)


class Profile(BaseModel):
    name: str
    contact: Contact = Field(default_factory=Contact)
    education: Education = Field(default_factory=Education)
    experience: List[Experience] = Field(default_factory=list)
    skills: Dict[str, List[str]] = Field(default_factory=dict)
    include_internships: bool = True
    always_include: List[str] = Field(default_factory=list)


# ---------- Parsed JD ----------

class ParsedJD(BaseModel):
    company: str = ""
    role_title: str = ""
    required_skills: List[str] = Field(default_factory=list)
    nice_to_have_skills: List[str] = Field(default_factory=list)
    key_themes: List[str] = Field(default_factory=list)
    industry: str = ""
    experience_years: str = ""
    mission_keywords: List[str] = Field(default_factory=list)


# ---------- Match analysis ----------

class MatchAnalysis(BaseModel):
    strong_matches: List[str] = Field(default_factory=list)
    partial_matches: List[str] = Field(default_factory=list)
    nice_to_have_matched: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    include_internships: bool = True
    skill_changes: List[str] = Field(default_factory=list)
    bullet_changes: List[str] = Field(default_factory=list)
