#!/usr/bin/env python3
"""
Analyze salary parity between teaching and tenure-track faculty in CS at UIUC.
"""

import json
import statistics
from collections import defaultdict


def load_faculty():
    """Load faculty data from JSON."""
    with open('cs_faculty_salaries.json') as f:
        return json.load(f)


def get_primary_faculty_salary(faculty_entry):
    """
    Get the primary faculty position salary (excluding admin stipends).
    Returns the highest-paying position that is a faculty role (not BA staff class).
    """
    faculty_positions = [p for p in faculty_entry['positions']
                        if p['empl_class'] in ('AA', 'AB', 'AL', 'AM')
                        and p['present_salary'] > 0]
    if not faculty_positions:
        return 0
    return max(p['present_salary'] for p in faculty_positions)


def is_clean_appointment(faculty_entry):
    """
    Check if this is a clean single-track appointment (not split research/teaching).
    """
    faculty_positions = [p for p in faculty_entry['positions']
                        if p['empl_class'] in ('AA', 'AB', 'AL', 'AM')]

    if not faculty_positions:
        return False

    # Check if all faculty positions are the same track
    titles = [p['title'].upper() for p in faculty_positions]

    has_teaching = any('TCH' in t or 'TEACHING' in t or 'LECTURER' in t for t in titles)
    has_research = any('RES ' in t for t in titles)
    has_tenure_track = any('PROF' in t and 'TCH' not in t and 'RES' not in t and 'TEACHING' not in t
                          for t in titles)

    # Clean if only one track
    tracks = sum([has_teaching, has_research, has_tenure_track])
    return tracks <= 1


def normalize_rank(rank, faculty_type):
    """Normalize ranks for comparison."""
    if rank == 'senior_lecturer':
        return 'lecturer'  # Group with lecturers
    if rank == 'instructor':
        return 'assistant'  # Compare with assistant profs
    return rank


def main():
    data = load_faculty()

    print("=" * 70)
    print("SALARY PARITY ANALYSIS: Teaching vs Tenure-Track Faculty")
    print("Siebel School of Computing & Data Science, UIUC")
    print("Data: Gray Book 2025-26 (Present Salary)")
    print("=" * 70)

    # Separate by type and rank
    teaching_by_rank = defaultdict(list)
    tenure_by_rank = defaultdict(list)

    for f in data['faculty']:
        # Only consider full-time appointments
        if not f['is_full_time_here']:
            continue

        # Only consider clean appointments (not split)
        if not is_clean_appointment(f):
            print(f"Excluding split appointment: {f['name']}")
            continue

        faculty_type = f['faculty_type']
        rank = normalize_rank(f['rank'], faculty_type)
        primary_salary = get_primary_faculty_salary(f)

        if primary_salary == 0:
            continue

        if faculty_type == 'teaching':
            teaching_by_rank[rank].append({
                'name': f['name'],
                'salary': primary_salary,
                'total_salary': f['total_present_salary']
            })
        elif faculty_type == 'tenure_track':
            tenure_by_rank[rank].append({
                'name': f['name'],
                'salary': primary_salary,
                'total_salary': f['total_present_salary']
            })

    print("\n")

    # Analyze by rank
    for rank in ['full', 'associate', 'assistant']:
        teaching = teaching_by_rank.get(rank, [])
        tenure = tenure_by_rank.get(rank, [])

        print(f"\n{'='*70}")
        print(f"RANK: {rank.upper()} PROFESSOR")
        print(f"{'='*70}")

        if teaching:
            t_salaries = [f['salary'] for f in teaching]
            print(f"\nTeaching Track ({len(teaching)} faculty):")
            print(f"  Mean:   ${statistics.mean(t_salaries):>12,.2f}")
            print(f"  Median: ${statistics.median(t_salaries):>12,.2f}")
            print(f"  Min:    ${min(t_salaries):>12,.2f}")
            print(f"  Max:    ${max(t_salaries):>12,.2f}")
            if len(t_salaries) > 1:
                print(f"  StdDev: ${statistics.stdev(t_salaries):>12,.2f}")
        else:
            print(f"\nTeaching Track: No faculty at this rank")

        if tenure:
            r_salaries = [f['salary'] for f in tenure]
            print(f"\nTenure Track ({len(tenure)} faculty):")
            print(f"  Mean:   ${statistics.mean(r_salaries):>12,.2f}")
            print(f"  Median: ${statistics.median(r_salaries):>12,.2f}")
            print(f"  Min:    ${min(r_salaries):>12,.2f}")
            print(f"  Max:    ${max(r_salaries):>12,.2f}")
            if len(r_salaries) > 1:
                print(f"  StdDev: ${statistics.stdev(r_salaries):>12,.2f}")
        else:
            print(f"\nTenure Track: No faculty at this rank")

        # Parity analysis
        if teaching and tenure:
            t_mean = statistics.mean(t_salaries)
            r_mean = statistics.mean(r_salaries)
            t_median = statistics.median(t_salaries)
            r_median = statistics.median(r_salaries)

            print(f"\n--- PARITY COMPARISON ---")
            print(f"  Mean difference:   ${r_mean - t_mean:>12,.2f} ({(r_mean/t_mean - 1)*100:+.1f}%)")
            print(f"  Median difference: ${r_median - t_median:>12,.2f} ({(r_median/t_median - 1)*100:+.1f}%)")
            print(f"  Teaching/Tenure ratio: {t_mean/r_mean:.2%} (mean), {t_median/r_median:.2%} (median)")

    # Lecturer comparison
    lecturers = teaching_by_rank.get('lecturer', [])
    if lecturers:
        print(f"\n{'='*70}")
        print(f"LECTURERS (non-professorial teaching track)")
        print(f"{'='*70}")
        l_salaries = [f['salary'] for f in lecturers]
        print(f"\n{len(lecturers)} lecturers:")
        print(f"  Mean:   ${statistics.mean(l_salaries):>12,.2f}")
        print(f"  Median: ${statistics.median(l_salaries):>12,.2f}")
        print(f"  Range:  ${min(l_salaries):>12,.2f} - ${max(l_salaries):>12,.2f}")

    # Overall summary
    print(f"\n{'='*70}")
    print("OVERALL SUMMARY")
    print(f"{'='*70}")

    all_teaching = [f for rank_list in teaching_by_rank.values() for f in rank_list]
    all_tenure = [f for rank_list in tenure_by_rank.values() for f in rank_list]

    print(f"\nTotal faculty analyzed:")
    print(f"  Teaching track: {len(all_teaching)}")
    print(f"  Tenure track:   {len(all_tenure)}")

    if all_teaching:
        t_all = [f['salary'] for f in all_teaching]
        print(f"\nTeaching track overall:")
        print(f"  Mean:   ${statistics.mean(t_all):>12,.2f}")
        print(f"  Median: ${statistics.median(t_all):>12,.2f}")

    if all_tenure:
        r_all = [f['salary'] for f in all_tenure]
        print(f"\nTenure track overall:")
        print(f"  Mean:   ${statistics.mean(r_all):>12,.2f}")
        print(f"  Median: ${statistics.median(r_all):>12,.2f}")

    # Individual faculty lists
    print(f"\n{'='*70}")
    print("TEACHING TRACK FACULTY (sorted by salary)")
    print(f"{'='*70}")
    for f in sorted(all_teaching, key=lambda x: x['salary'], reverse=True):
        print(f"  {f['name']:45} ${f['salary']:>12,.2f}")

    print(f"\n{'='*70}")
    print("TENURE TRACK FACULTY - TOP 30 (sorted by salary)")
    print(f"{'='*70}")
    for f in sorted(all_tenure, key=lambda x: x['salary'], reverse=True)[:30]:
        print(f"  {f['name']:45} ${f['salary']:>12,.2f}")


if __name__ == "__main__":
    main()
