import { parse } from "node-html-parser";
import { readFileSync, writeFileSync } from "fs";
import { resolve } from "path";
import type {
  Position,
  FacultyMember,
  FacultyData,
  DepartmentData,
  FacultyType,
  Rank,
} from "./types";

const HTML_FILE = resolve(import.meta.dir, "../uiuc-graybook.html");
const OUTPUT_JSON = resolve(import.meta.dir, "../cs_faculty_salaries.json");
const OUTPUT_CSV = resolve(import.meta.dir, "../cs_faculty_salaries.csv");

function parseSalary(salaryStr: string): number {
  const cleaned = salaryStr.replace(/[$,]/g, "").trim();
  return parseFloat(cleaned) || 0;
}

function parseFte(fteStr: string): number {
  return parseFloat(fteStr.trim()) || 0;
}

function getPrimaryPosition(positions: Position[]): Position | null {
  if (positions.length === 0) return null;
  const nonzero = positions.filter((p) => p.presentSalary > 0);
  if (nonzero.length > 0) {
    return nonzero.reduce((max, p) =>
      p.presentSalary > max.presentSalary ? p : max
    );
  }
  return positions[0];
}

function getFacultyType(positions: Position[]): FacultyType {
  const primary = getPrimaryPosition(positions);
  if (!primary) return "unknown";

  const title = primary.title.toUpperCase();

  if (
    ["TCH ", "TEACHING", "SR. LECTURER", "SR LECTURER", "LECTURER"].some((kw) =>
      title.includes(kw)
    )
  ) {
    return "teaching";
  }

  if (
    title.includes("RES ") &&
    (title.includes("PROF") || title.includes("ASSOC") || title.includes("ASST"))
  ) {
    return "research";
  }

  if (title.includes("CLIN") || title.includes("CLINICAL")) {
    return "clinical";
  }

  if (title.includes("PROF")) {
    return "tenure_track";
  }

  if (title.includes("INSTR")) {
    return "teaching";
  }

  return "other";
}

function getRank(positions: Position[]): Rank {
  const primary = getPrimaryPosition(positions);
  if (!primary) return "unknown";

  const title = primary.title.toUpperCase();

  if (title.includes("ASST PROF") || title.includes("ASSISTANT PROF")) {
    return "assistant";
  }
  if (title.includes("ASSOC PROF") || title.includes("ASSOCIATE PROF")) {
    return "associate";
  }
  if (title.includes("PROF")) {
    return "full";
  }
  if (title.includes("SR") && title.includes("LECTURER")) {
    return "senior_lecturer";
  }
  if (title.includes("LECTURER")) {
    return "lecturer";
  }
  if (title.includes("INSTR")) {
    return "instructor";
  }

  return "other";
}

function extractDepartmentNames(
  html: string
): Map<string, string> {
  const pattern = /<h3 id="([^"]+)">(\d+ - [^<]+)<\/h3>/g;
  const result = new Map<string, string>();
  let match;
  while ((match = pattern.exec(html)) !== null) {
    result.set(match[1], match[2]);
  }
  return result;
}

function parseGraybook(htmlPath: string): Map<string, FacultyMember[]> {
  const htmlContent = readFileSync(htmlPath, "utf-8");
  const root = parse(htmlContent);
  const departments = new Map<string, FacultyMember[]>();

  let currentDeptId: string | null = null;

  // Find all h3 elements (department headers) and their following tables
  const h3Elements = root.querySelectorAll("h3");

  for (const h3 of h3Elements) {
    const deptId = h3.getAttribute("id");
    if (!deptId) continue;

    currentDeptId = deptId;
    departments.set(deptId, []);

    // Find the table that follows this h3
    const table = h3.nextElementSibling;
    if (!table || table.tagName !== "TABLE") continue;

    const rows = table.querySelectorAll("tbody tr, tr");

    for (const row of rows) {
      const cells = row.querySelectorAll("td");
      if (cells.length < 8) continue;

      const name = cells[0].textContent.trim();
      const title = cells[1].textContent.trim();

      // Skip "Employee Total" rows
      if (title.includes("Employee Total")) continue;

      const tenure = cells[2].textContent.trim();
      const emplClass = cells[3].textContent.trim();
      const presentFte = parseFte(cells[4].textContent);
      const proposedFte = parseFte(cells[5].textContent);
      const presentSalary = parseSalary(cells[6].textContent);
      const proposedSalary = parseSalary(cells[7].textContent);

      const position: Position = {
        title,
        tenureCode: tenure,
        emplClass,
        presentFte,
        proposedFte,
        presentSalary,
        proposedSalary,
      };

      const deptFaculty = departments.get(currentDeptId)!;

      // Check if this is a continuation of the previous person
      if (
        deptFaculty.length > 0 &&
        (!name || name === deptFaculty[deptFaculty.length - 1].name)
      ) {
        deptFaculty[deptFaculty.length - 1].positions.push(position);
      } else {
        deptFaculty.push({
          name,
          department: currentDeptId,
          positions: [position],
        });
      }
    }
  }

  return departments;
}

function processFaculty(member: FacultyMember): FacultyData {
  const totalPresentSalary = member.positions.reduce(
    (sum, p) => sum + p.presentSalary,
    0
  );
  const totalProposedSalary = member.positions.reduce(
    (sum, p) => sum + p.proposedSalary,
    0
  );
  const totalPresentFte = member.positions.reduce(
    (sum, p) => sum + p.presentFte,
    0
  );

  return {
    name: member.name,
    facultyType: getFacultyType(member.positions),
    rank: getRank(member.positions),
    isFullTimeHere: totalPresentFte >= 0.9,
    isJointAppointment: totalPresentFte < 0.9 || totalPresentSalary === 0,
    totalPresentSalary,
    totalProposedSalary,
    totalPresentFte,
    positions: member.positions,
  };
}

function main() {
  console.log(`Reading ${HTML_FILE}...`);

  const htmlContent = readFileSync(HTML_FILE, "utf-8");
  const deptNames = extractDepartmentNames(htmlContent);
  console.log(`Found ${deptNames.size} departments`);

  // Find CS department
  let csDeptId: string | null = null;
  let csDeptName: string | null = null;
  for (const [id, name] of deptNames) {
    if (name.includes("Siebel School") || name.includes("434 -")) {
      csDeptId = id;
      csDeptName = name;
      console.log(`Found CS department: ${name} (ID: ${id})`);
      break;
    }
  }

  if (!csDeptId) {
    console.error("Could not find Siebel School department!");
    process.exit(1);
  }

  console.log("Parsing HTML tables...");
  const departments = parseGraybook(HTML_FILE);

  const csFaculty = departments.get(csDeptId);
  if (!csFaculty) {
    console.error(`Department ${csDeptId} not found in parsed data`);
    process.exit(1);
  }

  console.log(`\nFound ${csFaculty.length} entries in Siebel School`);

  // Process and filter faculty
  const allFaculty = csFaculty.map(processFaculty);
  const facultyOnly = allFaculty.filter((f) => {
    const primary = getPrimaryPosition(f.positions);
    return primary && ["AA", "AB", "AL", "AM"].includes(primary.emplClass);
  });

  console.log(`Faculty members (excluding staff): ${facultyOnly.length}`);

  // Categorize
  const teaching = facultyOnly.filter((f) => f.facultyType === "teaching");
  const tenureTrack = facultyOnly.filter((f) => f.facultyType === "tenure_track");
  const research = facultyOnly.filter((f) => f.facultyType === "research");
  const clinical = facultyOnly.filter((f) => f.facultyType === "clinical");

  console.log("\nBy faculty type:");
  console.log(`  Teaching track: ${teaching.length}`);
  console.log(`  Tenure track/tenured: ${tenureTrack.length}`);
  console.log(`  Research: ${research.length}`);
  console.log(`  Clinical: ${clinical.length}`);

  const teachingFt = teaching.filter((f) => f.isFullTimeHere);
  const tenureFt = tenureTrack.filter((f) => f.isFullTimeHere);

  console.log("\nFull-time in this department:");
  console.log(`  Teaching track: ${teachingFt.length}`);
  console.log(`  Tenure track: ${tenureFt.length}`);

  // Build output
  const output: DepartmentData = {
    department: csDeptName!,
    summary: {
      totalFaculty: facultyOnly.length,
      teachingTrack: teaching.length,
      teachingTrackFulltime: teachingFt.length,
      tenureTrack: tenureTrack.length,
      tenureTrackFulltime: tenureFt.length,
      research: research.length,
      clinical: clinical.length,
    },
    faculty: facultyOnly,
  };

  writeFileSync(OUTPUT_JSON, JSON.stringify(output, null, 2));
  console.log(`\nSaved detailed data to ${OUTPUT_JSON}`);

  // Generate CSV
  const csvHeader = [
    "Name",
    "Faculty Type",
    "Rank",
    "Full Time",
    "Joint Appt",
    "Present Salary",
    "Proposed Salary",
    "FTE",
    "Primary Title",
  ].join(",");

  const csvRows = facultyOnly.map((f) => {
    const primary = getPrimaryPosition(f.positions);
    return [
      `"${f.name}"`,
      f.facultyType,
      f.rank,
      f.isFullTimeHere,
      f.isJointAppointment,
      f.totalPresentSalary,
      f.totalProposedSalary,
      f.totalPresentFte,
      `"${primary?.title || ""}"`,
    ].join(",");
  });

  writeFileSync(OUTPUT_CSV, [csvHeader, ...csvRows].join("\n"));
  console.log(`Saved CSV to ${OUTPUT_CSV}`);
}

main();
