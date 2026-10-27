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

export type Dossier = { procedure: Procedure; documents: DossierDocument[]; answers: QA[] };

export type AgentReply = {
  session_id: string;
  type: "question" | "dossier" | "not_found";
  question: AgentQuestion | null;
  dossier: Dossier | null;
  message: string | null;
};
