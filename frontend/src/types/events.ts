/**
 * Event types shared between server and client
 */

export interface AnswerData {
  type: 'answer'
  answer: string
  timestamp: string
  model?: string
  messageId?: string
}

export interface ProcessingData {
  type: 'processing'
  timestamp: string
  messageId?: string
}

export type EventData = AnswerData | ProcessingData

// Parsed answer structures for different question types
export interface SingleChoiceAnswer {
  type: 'single'
  answer: string
  options?: string[]
  correct_index?: number
}

export interface MultipleChoiceAnswer {
  type: 'multiple'
  answers: string[]
  options?: string[]
  correct_indices?: number[]
}

export interface DragDropAnswer {
  type: 'dragdrop'
  mappings: Array<{ item: string; target: string }>
}

export interface HotAreaAnswer {
  type: 'hotarea'
  selections: Array<{ row: string; column: string }>
}

export interface SequenceAnswer {
  type: 'sequence'
  steps: string[]
}

export interface MatchingAnswer {
  type: 'matching'
  pairs: Array<{ left: string; right: string }>
}

export interface YesNoAnswer {
  type: 'yesno'
  statements: Array<{ statement: string; answer: string }>
}

export interface CaseStudyAnswer {
  type: 'casestudy'
  context?: string
  answers: Array<{ question: string; answer: string }>
}

export interface ErrorAnswer {
  type: 'error'
  message: string
}

/**
 * Common fields for enhanced answers with confidence tracking
 */
export interface ConfidenceMetadata {
  confidence?: number       // 0-100 confidence level
  verified?: boolean        // true if web_search was used
  sources?: string[]        // URLs consulted for verification
}

export type ParsedAnswer = (
  | SingleChoiceAnswer
  | MultipleChoiceAnswer
  | DragDropAnswer
  | HotAreaAnswer
  | SequenceAnswer
  | MatchingAnswer
  | YesNoAnswer
  | CaseStudyAnswer
  | ErrorAnswer
) & ConfidenceMetadata
