#!/usr/bin/env python3
"""
Parse University of Illinois Gray Book DOCX data to extract faculty salary information.
Focuses on distinguishing teaching vs research (tenure-track) faculty and handling joint appointments.
"""

import xml.etree.ElementTree as ET
import re
import json
from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path


@dataclass
class Position:
    """A single position/appointment for a faculty member."""
    title: str
    tenure_code: str
    empl_class: str
    present_fte: float
    proposed_fte: float
    present_salary: float
    proposed_salary: float


@dataclass
class FacultyMember:
    """A faculty member with potentially multiple positions."""
    name: str
    positions: List[Position]
    total_present_fte: float = 0.0
    total_proposed_fte: float = 0.0
    total_present_salary: float = 0.0
    total_proposed_salary: float = 0.0

    def __post_init__(self):
        # Calculate totals from positions
        self.total_present_fte = sum(p.present_fte for p in self.positions)
        self.total_proposed_fte = sum(p.proposed_fte for p in self.positions)
        self.total_present_salary = sum(p.present_salary for p in self.positions)
        self.total_proposed_salary = sum(p.proposed_salary for p in self.positions)

    @property
    def primary_position(self) -> Optional[Position]:
        """Return the position with the highest salary (primary appointment)."""
        if not self.positions:
            return None
        return max(self.positions, key=lambda p: p.present_salary)

    @property
    def faculty_type(self) -> str:
        """
        Determine if this is a teaching or research faculty member.
        Based on the primary position (highest paying).
        """
        primary = self.primary_position
        if not primary:
            return "unknown"

        title = primary.title.upper()

        # Teaching track indicators
        teaching_keywords = ['TCH ', 'TEACHING', 'LECTURER', 'INSTR ']
        if any(kw in title for kw in teaching_keywords):
            return "teaching"

        # Research track (typically adjunct or soft money)
        if 'RES ' in title and 'PROF' in title:
            return "research_only"

        # Clinical faculty
        if 'CLIN' in title or 'CLINICAL' in title:
            return "clinical"

        # Tenure-track/tenured (PROF, ASSOC PROF, ASST PROF without TCH prefix)
        if 'PROF' in title:
            return "tenure_track"

        return "other"

    @property
    def rank(self) -> str:
        """Determine faculty rank from primary position."""
        primary = self.primary_position
        if not primary:
            return "unknown"

        title = primary.title.upper()

        if 'ASST PROF' in title or 'ASSISTANT' in title:
            return "assistant"
        elif 'ASSOC PROF' in title or 'ASSOCIATE' in title:
            return "associate"
        elif 'PROF' in title:
            return "full"
        elif 'LECTURER' in title:
            if 'SR' in title:
                return "senior_lecturer"
            return "lecturer"
        elif 'INSTR' in title:
            return "instructor"

        return "other"

    @property
    def is_full_time(self) -> bool:
        """Check if this is a full-time appointment (FTE >= 0.9)."""
        return self.total_present_fte >= 0.9


def parse_salary(salary_str: str) -> float:
    """Parse a salary string like '$123,456.78' to float."""
    cleaned = salary_str.replace('$', '').replace(',', '')
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def extract_text_from_docx(docx_path: str) -> str:
    """Extract all text content from a DOCX file."""
    import zipfile

    with zipfile.ZipFile(docx_path, 'r') as zf:
        xml_content = zf.read('word/document.xml')

    tree = ET.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

    text_parts = []
    for elem in tree.iter():
        if elem.tag == '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t':
            if elem.text:
                text_parts.append(elem.text)

    return ' '.join(text_parts)


def extract_department_section(full_text: str, dept_code: str, dept_name: str) -> str:
    """Extract all pages of a department's section from the Gray Book text."""
    pattern = f'{dept_code} - {dept_name}'
    matches = list(re.finditer(re.escape(pattern), full_text))

    if not matches:
        raise ValueError(f"Department not found: {pattern}")

    sections = []
    for match in matches:
        start = match.start()
        # Find next page break
        remaining = full_text[start + len(pattern):]
        page_break = re.search(r'August \d+, 2025 Board of Trustees', remaining)
        if page_break:
            end = start + len(pattern) + page_break.start()
        else:
            end = start + 10000
        sections.append(full_text[start:end])

    return ' '.join(sections)


def parse_faculty_entries(text: str) -> List[FacultyMember]:
    """
    Parse faculty entries from department text.

    Format example:
    Challen, Geoffrey Werner TCH PROF M AA 1 1 $175,424.00 $179,999.60
    """
    faculty = []
    current_name = None
    current_positions = []

    # Pattern for a position line
    # Name, Title, Tenure, Class, Present FTE, Proposed FTE, Present Salary, Proposed Salary
    position_pattern = re.compile(
        r'([A-Z][a-z]+(?:[-\s][A-Z][a-z]+)*,\s+[A-Z][A-Za-z\s]+?)\s+'  # Name (Last, First Middle)
        r'([A-Z][A-Z &,]+?)\s+'  # Title (all caps with spaces/&/commas)
        r'([AMP]?[ABLM]?)\s+'  # Tenure code (A, P, M, AA, AB, AL, AM, etc.)
        r'(\d+(?:\.\d+)?)\s+'  # Present FTE
        r'(\d+(?:\.\d+)?)\s+'  # Proposed FTE
        r'\$([0-9,]+\.\d{2})\s+'  # Present Salary
        r'\$([0-9,]+\.\d{2})'  # Proposed Salary
    )

    # Alternative: simpler approach - split by known patterns
    # Let's try a line-by-line approach

    # First, let's identify where names start (Last, First pattern)
    name_pattern = re.compile(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s+[A-Z][a-z]+(?:\s[A-Z]\.?)?(?:\s[A-Z][a-z]+)*)')

    # Find all potential salary entries
    salary_pattern = re.compile(
        r'\$(\d{1,3}(?:,\d{3})*\.\d{2})\s+\$(\d{1,3}(?:,\d{3})*\.\d{2})'
    )

    # For each name, find the associated salaries
    # This is tricky because the format isn't perfectly structured

    # Let's use a different approach: find "Employee Total for All Jobs..." markers
    # which indicate the end of a person's entries

    entries = text.split('Employee Total for All Jobs...')

    for entry in entries:
        if not entry.strip():
            continue

        # Find the last name pattern in this entry (the person's name)
        names = list(name_pattern.finditer(entry))
        if not names:
            continue

        # The last name match is usually the person
        name_match = names[-1] if names else None
        if not name_match:
            continue

        name = name_match.group(1).strip()

        # Skip if this looks like a department header
        if 'Siebel School' in name or 'Engineering' in name:
            continue

        # Find salary pairs after the name
        name_end = name_match.end()
        remaining = entry[name_end:]

        salaries = list(salary_pattern.finditer(remaining))

        positions = []
        for sal in salaries:
            # Extract the text before this salary to get title info
            before_salary = remaining[:sal.start()].strip()

            # Try to parse title, tenure code, FTE from before_salary
            # Pattern: TITLE TENURE FTE FTE
            title_match = re.search(
                r'([A-Z][A-Z &,\.]+?)\s+([AMP]?[ABLM]?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*$',
                before_salary
            )

            if title_match:
                title = title_match.group(1).strip()
                tenure_code = title_match.group(2)
                present_fte = float(title_match.group(3))
                proposed_fte = float(title_match.group(4))
            else:
                # Simplified fallback
                title = before_salary.split()[-3] if len(before_salary.split()) > 3 else "UNKNOWN"
                tenure_code = ""
                present_fte = 1.0
                proposed_fte = 1.0

            present_salary = parse_salary(sal.group(1))
            proposed_salary = parse_salary(sal.group(2))

            positions.append(Position(
                title=title,
                tenure_code=tenure_code,
                empl_class="",
                present_fte=present_fte,
                proposed_fte=proposed_fte,
                present_salary=present_salary,
                proposed_salary=proposed_salary
            ))

        if positions:
            faculty.append(FacultyMember(name=name, positions=positions))

    return faculty


def parse_faculty_simple(text: str) -> List[FacultyMember]:
    """
    Simpler parsing approach: extract name, title, and salary from each entry.
    Uses Employee Total lines to determine total compensation.
    """
    faculty = []

    # Split text into person blocks (between consecutive names or Employee Total markers)
    # Pattern to match: Name Title Tenure Class FTE FTE $Salary $Salary
    entry_pattern = re.compile(
        r'([A-Z][a-z]+(?:[-\'][A-Z]?[a-z]+)?,\s+[A-Za-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Za-z]+)*)\s+'  # Name
        r'([A-Z][A-Z &,\.\']+?)\s+'  # Title (uppercase words)
        r'([AMP]{0,2})\s+'  # Tenure code
        r'(\d+(?:\.\d+)?)\s+'  # Present FTE
        r'(\d+(?:\.\d+)?)\s+'  # Proposed FTE
        r'\$(\d{1,3}(?:,\d{3})*\.\d{2})\s+'  # Present Salary
        r'\$(\d{1,3}(?:,\d{3})*\.\d{2})'  # Proposed Salary
    )

    # Also find Employee Total lines for total compensation
    total_pattern = re.compile(
        r'Employee Total for All Jobs\.\.\.\s+'
        r'(\d+(?:\.\d+)?)\s+'  # Total Present FTE
        r'(\d+(?:\.\d+)?)\s+'  # Total Proposed FTE
        r'\$(\d{1,3}(?:,\d{3})*\.\d{2})\s+'  # Total Present Salary
        r'\$(\d{1,3}(?:,\d{3})*\.\d{2})'  # Total Proposed Salary
    )

    current_name = None
    current_positions = []
    last_end = 0

    for match in entry_pattern.finditer(text):
        name = match.group(1).strip()
        title = match.group(2).strip()
        tenure = match.group(3)
        present_fte = float(match.group(4))
        proposed_fte = float(match.group(5))
        present_salary = parse_salary(match.group(6))
        proposed_salary = parse_salary(match.group(7))

        # Skip non-faculty entries (staff positions have BA class typically shown differently)
        # Skip entries that look like department headers
        if 'Siebel School' in name or 'Engineering' in name or 'Board of Trustees' in name:
            continue

        # Check if this is a new person or additional position for same person
        if current_name and name != current_name:
            # Save previous person
            if current_positions:
                faculty.append(FacultyMember(name=current_name, positions=current_positions))
            current_positions = []

        current_name = name
        current_positions.append(Position(
            title=title,
            tenure_code=tenure,
            empl_class="",
            present_fte=present_fte,
            proposed_fte=proposed_fte,
            present_salary=present_salary,
            proposed_salary=proposed_salary
        ))

    # Don't forget the last person
    if current_name and current_positions:
        faculty.append(FacultyMember(name=current_name, positions=current_positions))

    return faculty


def main():
    """Main entry point."""
    docx_path = "gray-book-urbana-25-26.docx"

    # Extract text from DOCX
    print(f"Reading {docx_path}...")
    full_text = extract_text_from_docx(docx_path)

    # Extract Siebel School section
    print("Extracting Siebel School of Computing & Data Science section...")
    cs_text = extract_department_section(full_text, "434", "Siebel School Comp & Data Sci")

    # Parse faculty entries
    print("Parsing faculty entries...")
    faculty = parse_faculty_simple(cs_text)

    print(f"\nFound {len(faculty)} faculty members")

    # Categorize by type
    teaching = [f for f in faculty if f.faculty_type == "teaching"]
    tenure_track = [f for f in faculty if f.faculty_type == "tenure_track"]
    research = [f for f in faculty if f.faculty_type == "research_only"]
    clinical = [f for f in faculty if f.faculty_type == "clinical"]
    other = [f for f in faculty if f.faculty_type == "other"]

    print(f"\nBy faculty type:")
    print(f"  Teaching faculty: {len(teaching)}")
    print(f"  Tenure-track/tenured: {len(tenure_track)}")
    print(f"  Research-only: {len(research)}")
    print(f"  Clinical: {len(clinical)}")
    print(f"  Other: {len(other)}")

    # Save to JSON
    output = {
        "department": "Siebel School of Computing & Data Science",
        "faculty": [
            {
                "name": f.name,
                "faculty_type": f.faculty_type,
                "rank": f.rank,
                "is_full_time": f.is_full_time,
                "total_present_salary": f.total_present_salary,
                "total_proposed_salary": f.total_proposed_salary,
                "total_present_fte": f.total_present_fte,
                "positions": [asdict(p) for p in f.positions]
            }
            for f in faculty
        ]
    }

    with open("cs_faculty_salaries.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved to cs_faculty_salaries.json")

    return faculty


if __name__ == "__main__":
    main()
