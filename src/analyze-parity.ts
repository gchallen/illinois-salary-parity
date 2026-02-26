import { readFileSync } from "fs";
import { resolve } from "path";
import type { DepartmentData, FacultyData, Position } from "./types";

const DATA_FILE = resolve(import.meta.dir, "../cs_faculty_salaries.json");

function getPrimaryFacultySalary(faculty: FacultyData): number {
  const facultyPositions = faculty.positions.filter(
    (p) =>
      ["AA", "AB", "AL", "AM"].includes(p.emplClass) && p.presentSalary > 0
  );
  if (facultyPositions.length === 0) return 0;
  return Math.max(...facultyPositions.map((p) => p.presentSalary));
}

function isCleanAppointment(faculty: FacultyData): boolean {
  const facultyPositions = faculty.positions.filter((p) =>
    ["AA", "AB", "AL", "AM"].includes(p.emplClass)
  );

  if (facultyPositions.length === 0) return false;

  const titles = facultyPositions.map((p) => p.title.toUpperCase());

  const hasTeaching = titles.some(
    (t) => t.includes("TCH") || t.includes("TEACHING") || t.includes("LECTURER")
  );
  const hasResearch = titles.some((t) => t.includes("RES "));
  const hasTenureTrack = titles.some(
    (t) =>
      t.includes("PROF") &&
      !t.includes("TCH") &&
      !t.includes("RES") &&
      !t.includes("TEACHING")
  );

  const tracks = [hasTeaching, hasResearch, hasTenureTrack].filter(Boolean)
    .length;
  return tracks <= 1;
}

function normalizeRank(rank: string): string {
  if (rank === "senior_lecturer") return "lecturer";
  if (rank === "instructor") return "assistant";
  return rank;
}

function mean(values: number[]): number {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

function stdev(values: number[]): number {
  const m = mean(values);
  const squaredDiffs = values.map((v) => (v - m) ** 2);
  return Math.sqrt(mean(squaredDiffs));
}

function formatCurrency(value: number): string {
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

interface FacultyWithSalary {
  name: string;
  salary: number;
  totalSalary: number;
}

function main() {
  const data: DepartmentData = JSON.parse(readFileSync(DATA_FILE, "utf-8"));

  console.log("=".repeat(70));
  console.log("SALARY PARITY ANALYSIS: Teaching vs Tenure-Track Faculty");
  console.log("Siebel School of Computing & Data Science, UIUC");
  console.log("Data: Gray Book 2025-26 (Present Salary)");
  console.log("=".repeat(70));

  const teachingByRank = new Map<string, FacultyWithSalary[]>();
  const tenureByRank = new Map<string, FacultyWithSalary[]>();

  for (const f of data.faculty) {
    if (!f.isFullTimeHere) continue;
    if (!isCleanAppointment(f)) {
      console.log(`Excluding split appointment: ${f.name}`);
      continue;
    }

    const rank = normalizeRank(f.rank);
    const primarySalary = getPrimaryFacultySalary(f);

    if (primarySalary === 0) continue;

    const entry: FacultyWithSalary = {
      name: f.name,
      salary: primarySalary,
      totalSalary: f.totalPresentSalary,
    };

    if (f.facultyType === "teaching") {
      if (!teachingByRank.has(rank)) teachingByRank.set(rank, []);
      teachingByRank.get(rank)!.push(entry);
    } else if (f.facultyType === "tenure_track") {
      if (!tenureByRank.has(rank)) tenureByRank.set(rank, []);
      tenureByRank.get(rank)!.push(entry);
    }
  }

  console.log("\n");

  for (const rank of ["full", "associate", "assistant"]) {
    const teaching = teachingByRank.get(rank) || [];
    const tenure = tenureByRank.get(rank) || [];

    console.log("\n" + "=".repeat(70));
    console.log(`RANK: ${rank.toUpperCase()} PROFESSOR`);
    console.log("=".repeat(70));

    if (teaching.length > 0) {
      const tSalaries = teaching.map((f) => f.salary);
      console.log(`\nTeaching Track (${teaching.length} faculty):`);
      console.log(`  Mean:   ${formatCurrency(mean(tSalaries)).padStart(15)}`);
      console.log(`  Median: ${formatCurrency(median(tSalaries)).padStart(15)}`);
      console.log(`  Min:    ${formatCurrency(Math.min(...tSalaries)).padStart(15)}`);
      console.log(`  Max:    ${formatCurrency(Math.max(...tSalaries)).padStart(15)}`);
      if (tSalaries.length > 1) {
        console.log(`  StdDev: ${formatCurrency(stdev(tSalaries)).padStart(15)}`);
      }
    } else {
      console.log("\nTeaching Track: No faculty at this rank");
    }

    if (tenure.length > 0) {
      const rSalaries = tenure.map((f) => f.salary);
      console.log(`\nTenure Track (${tenure.length} faculty):`);
      console.log(`  Mean:   ${formatCurrency(mean(rSalaries)).padStart(15)}`);
      console.log(`  Median: ${formatCurrency(median(rSalaries)).padStart(15)}`);
      console.log(`  Min:    ${formatCurrency(Math.min(...rSalaries)).padStart(15)}`);
      console.log(`  Max:    ${formatCurrency(Math.max(...rSalaries)).padStart(15)}`);
      if (rSalaries.length > 1) {
        console.log(`  StdDev: ${formatCurrency(stdev(rSalaries)).padStart(15)}`);
      }
    } else {
      console.log("\nTenure Track: No faculty at this rank");
    }

    if (teaching.length > 0 && tenure.length > 0) {
      const tSalaries = teaching.map((f) => f.salary);
      const rSalaries = tenure.map((f) => f.salary);
      const tMean = mean(tSalaries);
      const rMean = mean(rSalaries);
      const tMedian = median(tSalaries);
      const rMedian = median(rSalaries);

      console.log("\n--- PARITY COMPARISON ---");
      console.log(
        `  Mean difference:   ${formatCurrency(rMean - tMean).padStart(15)} (${((rMean / tMean - 1) * 100).toFixed(1)}%)`
      );
      console.log(
        `  Median difference: ${formatCurrency(rMedian - tMedian).padStart(15)} (${((rMedian / tMedian - 1) * 100).toFixed(1)}%)`
      );
      console.log(
        `  Teaching/Tenure ratio: ${((tMean / rMean) * 100).toFixed(2)}% (mean), ${((tMedian / rMedian) * 100).toFixed(2)}% (median)`
      );
    }
  }

  // Lecturer comparison
  const lecturers = teachingByRank.get("lecturer") || [];
  if (lecturers.length > 0) {
    console.log("\n" + "=".repeat(70));
    console.log("LECTURERS (non-professorial teaching track)");
    console.log("=".repeat(70));
    const lSalaries = lecturers.map((f) => f.salary);
    console.log(`\n${lecturers.length} lecturers:`);
    console.log(`  Mean:   ${formatCurrency(mean(lSalaries)).padStart(15)}`);
    console.log(`  Median: ${formatCurrency(median(lSalaries)).padStart(15)}`);
    console.log(
      `  Range:  ${formatCurrency(Math.min(...lSalaries)).padStart(15)} - ${formatCurrency(Math.max(...lSalaries))}`
    );
  }

  // Overall summary
  console.log("\n" + "=".repeat(70));
  console.log("OVERALL SUMMARY");
  console.log("=".repeat(70));

  const allTeaching = [...teachingByRank.values()].flat();
  const allTenure = [...tenureByRank.values()].flat();

  console.log("\nTotal faculty analyzed:");
  console.log(`  Teaching track: ${allTeaching.length}`);
  console.log(`  Tenure track:   ${allTenure.length}`);

  if (allTeaching.length > 0) {
    const tAll = allTeaching.map((f) => f.salary);
    console.log("\nTeaching track overall:");
    console.log(`  Mean:   ${formatCurrency(mean(tAll)).padStart(15)}`);
    console.log(`  Median: ${formatCurrency(median(tAll)).padStart(15)}`);
  }

  if (allTenure.length > 0) {
    const rAll = allTenure.map((f) => f.salary);
    console.log("\nTenure track overall:");
    console.log(`  Mean:   ${formatCurrency(mean(rAll)).padStart(15)}`);
    console.log(`  Median: ${formatCurrency(median(rAll)).padStart(15)}`);
  }

  // Individual faculty lists
  console.log("\n" + "=".repeat(70));
  console.log("TEACHING TRACK FACULTY (sorted by salary)");
  console.log("=".repeat(70));
  for (const f of allTeaching.sort((a, b) => b.salary - a.salary)) {
    console.log(`  ${f.name.padEnd(45)} ${formatCurrency(f.salary).padStart(15)}`);
  }

  console.log("\n" + "=".repeat(70));
  console.log("TENURE TRACK FACULTY - TOP 30 (sorted by salary)");
  console.log("=".repeat(70));
  for (const f of allTenure.sort((a, b) => b.salary - a.salary).slice(0, 30)) {
    console.log(`  ${f.name.padEnd(45)} ${formatCurrency(f.salary).padStart(15)}`);
  }
}

main();
