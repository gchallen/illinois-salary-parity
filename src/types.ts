export interface Position {
  title: string;
  tenureCode: string;
  emplClass: string;
  presentFte: number;
  proposedFte: number;
  presentSalary: number;
  proposedSalary: number;
}

export interface FacultyMember {
  name: string;
  department: string;
  positions: Position[];
}

export interface FacultyData {
  name: string;
  facultyType: FacultyType;
  rank: Rank;
  isFullTimeHere: boolean;
  isJointAppointment: boolean;
  totalPresentSalary: number;
  totalProposedSalary: number;
  totalPresentFte: number;
  positions: Position[];
}

export interface DepartmentData {
  department: string;
  summary: {
    totalFaculty: number;
    teachingTrack: number;
    teachingTrackFulltime: number;
    tenureTrack: number;
    tenureTrackFulltime: number;
    research: number;
    clinical: number;
  };
  faculty: FacultyData[];
}

export type FacultyType =
  | "teaching"
  | "tenure_track"
  | "research"
  | "clinical"
  | "other"
  | "unknown";

export type Rank =
  | "full"
  | "associate"
  | "assistant"
  | "senior_lecturer"
  | "lecturer"
  | "instructor"
  | "other"
  | "unknown";

export interface ChartDataPoint {
  track: "Teaching" | "Tenure-Track";
  rank: "Assistant" | "Associate" | "Full";
  salary: number;
}
