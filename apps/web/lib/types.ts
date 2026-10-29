// Mirrors the backend models in apps/api/src/hosoai (procedures/models.py, agent/matcher.py).

export type Source = {
  url: string;
  title: string;
  document_number: string | null;
  publisher: string | null;
  retrieved_at: string;
};

export type SourcedText = { text: string; source: Source };

export type RequiredDocument = {
  name: string;
  form_name: string | null;
  quantity: string | null;
  source: Source;
};

export type FormFile = { label: string; url: string; source: Source };

export type Procedure = {
  slug: string;
  title: string;
  national_code: string | null;
  field: SourcedText | null;
  agency: SourcedText | null;
  methods: SourcedText[];
  steps: SourcedText[];
  processing_time: SourcedText | null;
  fee: SourcedText | null;
  documents: RequiredDocument[];
  conditions: SourcedText | null;
  legal_basis: SourcedText[];
  result: SourcedText | null;
  forms: FormFile[];
  warnings: string[];
  source: Source;
};

export type ProcedureSummary = {
  slug: string;
  title: string;
  national_code: string | null;
  label_en: string | null;
  source: Source;
};

export type MatchResult = {
  status: "matched" | "ambiguous" | "not_found";
  candidates: ProcedureSummary[];
  message: string | null;
};

// Agent conversation (apps/api/src/hosoai/agent/loop.py)

export type DocRef = { id: string; name: string };

export type AgentQuestion = {
  number: number;
  kind: "case" | "choose_procedure";
  text: string;
  options: string[];
  about: DocRef[];
};

export type QA = { number: number; question: string; answer: string };

export type DocStatus = "needed" | "not_needed" | "unsure";

export type DossierDocument = {
  id: string;
  status: DocStatus;
  document: RequiredDocument;
  because: QA[];
};

export type Dossier = {
  procedure: Procedure;
  documents: DossierDocument[];
  answers: QA[];
  forms: FormSummary[]; // official forms we can fill for this procedure
};

export type AgentReply = {
  session_id: string;
  type: "question" | "dossier" | "not_found";
  question: AgentQuestion | null;
  dossier: Dossier | null;
  message: string | null;
};

// Saved profile (apps/api/src/hosoai/profile/models.py)
export type Profile = {
  full_name: string | null;
  date_of_birth: string | null; // YYYY-MM-DD
  sex: "Nam" | "Nữ" | null;
  id_number: string | null;
  nationality: string | null;
  ethnicity: string | null;
  religion: string | null;
  place_of_birth: string | null;
  hometown: string | null;
  permanent_address: string | null;
  current_address: string | null;
  occupation: string | null;
  phone: string | null;
  email: string | null;
  passport_number: string | null;
};

// Fillable official forms (apps/api/src/hosoai/forms/models.py)
export type FormField = {
  key: string;
  label: string; // exact text printed on the official form
  hint: string | null; // our own short gloss, not official text
  profile_key: keyof Profile | null;
  page: number;
  mode: "after_label" | "boxes" | "date_parts" | "choice" | "acroform" | "region";
  max_chars: number | null;
};

export type FormSpec = {
  id: string;
  code: string;
  title: string;
  procedure_slugs: string[];
  source: Source;
  fields: FormField[];
  notes: string[];
  preview_pages: number;
  status: "reviewed" | "draft"; // draft = read by the form-learning agent, not yet human-reviewed
};

export type FormSummary = Pick<FormSpec, "id" | "code" | "title" | "procedure_slugs" | "source">;

/** A form linked from the official procedure page, and whether we can fill it yet. */
export type OfficialForm = {
  index: number;
  label: string;
  url: string;
  form_id: string | null;
  status: "reviewed" | "draft" | null;
};

export type LearnResult = {
  form: FormSummary;
  report: {
    rounds: number;
    candidates: number;
    accepted: string[];
    rejected: Record<string, string>;
  };
};

export type FormDetail = { spec: FormSpec; values: Record<string, string> };
