#!/usr/bin/env python3
"""
Parse University of Illinois Gray Book HTML data to extract faculty salary information.
Uses the structured HTML tables which are much cleaner than the DOCX format.
"""

import re
import json
import csv
from html.parser import HTMLParser
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
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
    """A faculty member with potentially multiple positions in this department."""
    name: str
    department: str
    positions: List[Position] = field(default_factory=list)

    @property
    def primary_position(self) -> Optional[Position]:
        """Return the position with the highest salary (primary appointment in this dept)."""
        if not self.positions:
            return None
        # Filter out $0 positions first
        nonzero = [p for p in self.positions if p.present_salary > 0]
        if nonzero:
            return max(nonzero, key=lambda p: p.present_salary)
        return self.positions[0]

    @property
    def total_present_salary(self) -> float:
        """Total salary from all positions in this department."""
        return sum(p.present_salary for p in self.positions)

    @property
    def total_proposed_salary(self) -> float:
        return sum(p.proposed_salary for p in self.positions)

    @property
    def total_present_fte(self) -> float:
        return sum(p.present_fte for p in self.positions)

    @property
    def faculty_type(self) -> str:
        """
        Determine faculty type based on primary position title.
        """
        primary = self.primary_position
        if not primary:
            return "unknown"

        title = primary.title.upper()

        # Teaching track indicators
        if any(kw in title for kw in ['TCH ', 'TEACHING', 'SR. LECTURER', 'SR LECTURER', 'LECTURER']):
            return "teaching"

        # Research-only faculty (soft money, not tenure track)
        if 'RES ' in title and ('PROF' in title or 'ASSOC' in title or 'ASST' in title):
            return "research"

        # Clinical faculty
        if 'CLIN' in title or 'CLINICAL' in title:
            return "clinical"

        # Tenure-track/tenured - regular PROF/ASSOC PROF/ASST PROF without TCH prefix
        if 'PROF' in title:
            return "tenure_track"

        # Instructors (may be teaching track)
        if 'INSTR' in title:
            return "teaching"

        return "other"

    @property
    def rank(self) -> str:
        """Determine faculty rank from primary position."""
        primary = self.primary_position
        if not primary:
            return "unknown"

        title = primary.title.upper()

        if 'ASST PROF' in title or 'ASSISTANT PROF' in title:
            return "assistant"
        elif 'ASSOC PROF' in title or 'ASSOCIATE PROF' in title:
            return "associate"
        elif 'PROF' in title:  # Full professor (must check after asst/assoc)
            return "full"
        elif 'SR' in title and 'LECTURER' in title:
            return "senior_lecturer"
        elif 'LECTURER' in title:
            return "lecturer"
        elif 'INSTR' in title:
            return "instructor"

        return "other"

    @property
    def is_joint_appointment(self) -> bool:
        """Check if this appears to be a joint appointment (FTE < 1 or $0 primary)."""
        return self.total_present_fte < 0.9 or self.total_present_salary == 0

    @property
    def is_full_time_here(self) -> bool:
        """Check if this is a full-time appointment in this department."""
        return self.total_present_fte >= 0.9


def parse_salary(salary_str: str) -> float:
    """Parse a salary string like '$123,456.78' to float."""
    cleaned = salary_str.replace('$', '').replace(',', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_fte(fte_str: str) -> float:
    """Parse FTE string to float."""
    try:
        return float(fte_str.strip())
    except ValueError:
        return 0.0


class GrayBookHTMLParser(HTMLParser):
    """Parse Gray Book HTML to extract faculty data."""

    def __init__(self):
        super().__init__()
        self.departments = {}  # dept_id -> {"name": str, "faculty": [FacultyMember]}
        self.current_dept_id = None
        self.current_dept_name = None
        self.in_table = False
        self.in_thead = False
        self.in_row = False
        self.in_cell = False
        self.current_row = []
        self.current_cell_text = ""
        self.college = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'h2':
            # College header like "KP - Grainger Engineering"
            self.college = None

        if tag == 'h3':
            # Department header - extract ID
            if 'id' in attrs_dict:
                self.current_dept_id = attrs_dict['id']

        if tag == 'table':
            self.in_table = True

        if tag == 'thead':
            self.in_thead = True

        if tag == 'tr' and self.in_table and not self.in_thead:
            self.in_row = True
            self.current_row = []

        if tag in ('td', 'th') and self.in_row:
            self.in_cell = True
            self.current_cell_text = ""

    def handle_endtag(self, tag):
        if tag == 'thead':
            self.in_thead = False

        if tag == 'table':
            self.in_table = False

        if tag in ('td', 'th') and self.in_cell:
            self.in_cell = False
            self.current_row.append(self.current_cell_text.strip())

        if tag == 'tr' and self.in_row:
            self.in_row = False
            if self.current_row and self.current_dept_id:
                self._process_row(self.current_row)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell_text += data

        # Capture department names from h3 content
        # This is a bit hacky but works

    def _process_row(self, row):
        """Process a table row and add to current department."""
        if len(row) < 8:
            return

        name = row[0]
        title = row[1]

        # Skip "Employee Total" rows - we calculate totals ourselves
        if 'Employee Total' in title:
            return
        tenure = row[2]
        empl_class = row[3]
        present_fte = parse_fte(row[4])
        proposed_fte = parse_fte(row[5])
        present_salary = parse_salary(row[6])
        proposed_salary = parse_salary(row[7])

        if self.current_dept_id not in self.departments:
            self.departments[self.current_dept_id] = {
                "name": self.current_dept_id,
                "faculty": []
            }

        dept = self.departments[self.current_dept_id]

        # Check if this is a continuation of the previous person (same name, different position)
        # or a new position for same person (name might be empty or same)
        if dept["faculty"] and (not name or name == dept["faculty"][-1].name):
            # Additional position for same person
            dept["faculty"][-1].positions.append(Position(
                title=title,
                tenure_code=tenure,
                empl_class=empl_class,
                present_fte=present_fte,
                proposed_fte=proposed_fte,
                present_salary=present_salary,
                proposed_salary=proposed_salary
            ))
        else:
            # New faculty member
            faculty = FacultyMember(
                name=name,
                department=self.current_dept_id,
                positions=[Position(
                    title=title,
                    tenure_code=tenure,
                    empl_class=empl_class,
                    present_fte=present_fte,
                    proposed_fte=proposed_fte,
                    present_salary=present_salary,
                    proposed_salary=proposed_salary
                )]
            )
            dept["faculty"].append(faculty)


def parse_graybook_html(html_path: str) -> Dict:
    """Parse the Gray Book HTML file and return structured data."""
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    parser = GrayBookHTMLParser()
    parser.feed(html_content)

    return parser.departments


def extract_department_names(html_path: str) -> Dict[str, str]:
    """Extract department ID to name mapping from HTML."""
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Pattern: <h3 id="c42-d6">434 - Siebel School Comp &amp; Data Sci</h3>
    pattern = re.compile(r'<h3 id="([^"]+)">(\d+ - [^<]+)</h3>')
    matches = pattern.findall(html_content)

    return {m[0]: m[1] for m in matches}


def main():
    """Main entry point."""
    html_path = "uiuc-graybook.html"

    print(f"Reading {html_path}...")

    # Get department name mapping
    dept_names = extract_department_names(html_path)
    print(f"Found {len(dept_names)} departments")

    # Find CS department ID
    cs_dept_id = None
    for dept_id, name in dept_names.items():
        if 'Siebel School' in name or '434 -' in name:
            cs_dept_id = dept_id
            print(f"Found CS department: {name} (ID: {dept_id})")
            break

    if not cs_dept_id:
        print("Could not find Siebel School department!")
        return

    # Parse the HTML
    print("Parsing HTML tables...")
    departments = parse_graybook_html(html_path)

    if cs_dept_id not in departments:
        print(f"Department {cs_dept_id} not found in parsed data")
        print(f"Available departments: {list(departments.keys())[:10]}...")
        return

    cs_dept = departments[cs_dept_id]
    faculty = cs_dept["faculty"]

    print(f"\nFound {len(faculty)} entries in Siebel School")

    # Filter to actual faculty (not staff)
    # Staff typically have empl_class 'BA'
    faculty_only = [f for f in faculty if f.primary_position and
                    f.primary_position.empl_class in ('AA', 'AB', 'AL', 'AM')]

    print(f"Faculty members (excluding staff): {len(faculty_only)}")

    # Categorize
    teaching = [f for f in faculty_only if f.faculty_type == "teaching"]
    tenure_track = [f for f in faculty_only if f.faculty_type == "tenure_track"]
    research = [f for f in faculty_only if f.faculty_type == "research"]
    clinical = [f for f in faculty_only if f.faculty_type == "clinical"]
    other = [f for f in faculty_only if f.faculty_type == "other"]

    print(f"\nBy faculty type:")
    print(f"  Teaching track: {len(teaching)}")
    print(f"  Tenure track/tenured: {len(tenure_track)}")
    print(f"  Research: {len(research)}")
    print(f"  Clinical: {len(clinical)}")
    print(f"  Other: {len(other)}")

    # Further break down by full-time status
    teaching_ft = [f for f in teaching if f.is_full_time_here]
    tenure_ft = [f for f in tenure_track if f.is_full_time_here]

    print(f"\nFull-time in this department:")
    print(f"  Teaching track: {len(teaching_ft)}")
    print(f"  Tenure track: {len(tenure_ft)}")

    # Save detailed output
    output = {
        "department": dept_names.get(cs_dept_id, cs_dept_id),
        "summary": {
            "total_faculty": len(faculty_only),
            "teaching_track": len(teaching),
            "teaching_track_fulltime": len(teaching_ft),
            "tenure_track": len(tenure_track),
            "tenure_track_fulltime": len(tenure_ft),
            "research": len(research),
            "clinical": len(clinical),
        },
        "faculty": [
            {
                "name": f.name,
                "faculty_type": f.faculty_type,
                "rank": f.rank,
                "is_full_time_here": f.is_full_time_here,
                "is_joint_appointment": f.is_joint_appointment,
                "total_present_salary": f.total_present_salary,
                "total_proposed_salary": f.total_proposed_salary,
                "total_present_fte": f.total_present_fte,
                "positions": [asdict(p) for p in f.positions]
            }
            for f in faculty_only
        ]
    }

    with open("cs_faculty_salaries.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved detailed data to cs_faculty_salaries.json")

    # Also save a CSV for easy analysis
    with open("cs_faculty_salaries.csv", "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Name", "Faculty Type", "Rank", "Full Time", "Joint Appt",
            "Present Salary", "Proposed Salary", "FTE", "Primary Title"
        ])
        for fac in faculty_only:
            writer.writerow([
                fac.name,
                fac.faculty_type,
                fac.rank,
                fac.is_full_time_here,
                fac.is_joint_appointment,
                fac.total_present_salary,
                fac.total_proposed_salary,
                fac.total_present_fte,
                fac.primary_position.title if fac.primary_position else ""
            ])

    print("Saved CSV to cs_faculty_salaries.csv")

    return faculty_only


if __name__ == "__main__":
    main()
