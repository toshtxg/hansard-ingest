export interface OverviewStats {
  total_speeches: number
  total_sittings: number
  total_speakers: number
  total_words: number
  earliest_sitting: string
  latest_sitting: string
}

export interface RecentSitting {
  sitting_date: string
  source_url: string | null
  speech_count: number
  word_count: number
}

export interface MPListItem {
  mp_name: string
  total_words: number
  total_speeches: number
  sittings_active: number
  primary_section_type: string
}

export interface MPSummary {
  mp_name: string
  total_words: number
  total_speeches: number
  sittings_active: number
  first_sitting: string
  last_sitting: string
  parliaments: number[]
}

export interface MPActivityPoint {
  period: string
  word_count: number
  speech_count: number
}

export interface MPTopic {
  discussion_title: string
  word_count: number
  speech_count: number
  section_type: string
}

export interface MPSectionBreakdown {
  section_type: string
  speech_count: number
  word_count: number
}

export interface MPSpeech {
  sitting_date: string
  discussion_title: string
  section_type: string
  word_count: number
  one_liner: string | null
  source_url: string | null
}

export interface MPDiscussion {
  discussion_title: string
  sitting_date: string
  mp_words: number
  mp_speech_count: number
  primary_section_type: string
}

export interface TopicSpeaker {
  mp_name: string
  word_count: number
  one_liner: string | null
  themes: string[] | null
  section_type: string
  speech_details: string | null
  is_chair: boolean
}

export interface TopicResult {
  discussion_title: string
  sitting_date: string
  section_type: string
  speaker_count: number
  total_words: number
  parliament_no: number
}

export interface TopicDetail {
  discussion_title: string
  sitting_date: string
  source_url: string | null
  speakers: TopicSpeaker[]
}

export interface TrendsVolume {
  period: string
  section_type: string
  speech_count: number
  word_count: number
}

export interface ParliamentSummary {
  parliament_no: number
  date_range: string
  total_sittings: number
  total_speeches: number
  total_speakers: number
  avg_speeches_per_sitting: number
}

export interface SittingIntensity {
  period: string
  sitting_count: number
  avg_words_per_sitting: number
}

export interface SpeakerDiversity {
  period: string
  unique_speakers: number
  avg_words_per_speaker: number
}

export interface KeywordTrendPoint {
  period: string
  speech_count: number
  sitting_count: number
}

export interface KeywordSpeaker {
  mp_name: string
  speech_count: number
  sitting_count: number
}

export interface KeywordSpeakerDetail {
  sitting_date: string
  discussion_title: string
  times_spoken: number
  word_count: number
  section_type: string
  one_liner: string | null
}
