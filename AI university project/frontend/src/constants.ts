import type {
  ContentDepth, ContentType, FormatTier, LearningMethod, ModuleStatus, TopicStatus,
} from './types';

export const FORMAT_TIER_LABELS: Record<FormatTier, string> = {
  quick_dive: 'Quick Dive',
  deep_dive: 'Deep Dive',
  short_course: 'Short Course',
  full_course: 'Full Course',
};

export const FORMAT_TIER_DESCRIPTIONS: Record<FormatTier, string> = {
  quick_dive: 'One sitting, 1–2 hours. One research pass, one digest, one mixed exercise at the end.',
  deep_dive: 'A weekend. Deeper research, split across a few sessions with practice rounds in between.',
  short_course: 'About a week. 4–5 modules, researched one at a time as you go.',
  full_course: '2–3 weeks. A full curriculum with real prerequisite ordering, built and researched module by module.',
};

export const CONTENT_DEPTH_LABELS: Record<ContentDepth, string> = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
};

export const CONTENT_DEPTH_DESCRIPTIONS: Record<ContentDepth, string> = {
  beginner: 'Zero background assumed. Every term defined, intuition and examples over precision — fine to skip edge cases.',
  intermediate: 'Comfortable with moderate complexity. Real mechanics, not just surface intuition, without chasing every edge case.',
  advanced: 'Real technical depth and field-standard terminology. Engages with edge cases and nuance that actually matter.',
};

export const TOPIC_STATUS_LABELS: Record<TopicStatus, string> = {
  planning: 'Planning',
  active: 'In Progress',
  completed: 'Completed',
};

export const MODULE_STATUS_LABELS: Record<ModuleStatus, string> = {
  pending: 'Queued',
  researched: 'Ready',
  in_progress: 'In Progress',
  completed: 'Completed',
};

export const CONTENT_TYPE_LABELS: Record<ContentType, string> = {
  skill: 'Skill',
  conceptual: 'Conceptual',
  mixed: 'Mixed',
};

export interface MethodInfo {
  label: string;
  description: string;
}

export const METHOD_INFO: Record<LearningMethod, MethodInfo> = {
  teach_it_back: {
    label: 'Teach It Back',
    description: 'Explain it in your own words. I\'ll play dumb and poke holes.',
  },
  sparring: {
    label: 'Sparring',
    description: 'I\'ll argue a position — even a wrong one. Talk me out of it.',
  },
  ship_it: {
    label: 'Ship It',
    description: 'Produce something real. If it\'s code, it actually gets run.',
  },
  analogy_builder: {
    label: 'Analogy Builder',
    description: 'Explain it through an analogy, and I\'ll check whether it actually holds up.',
  },
  error_hunt: {
    label: 'Error Hunt',
    description: 'I\'ll show you something that looks right. Find what\'s wrong with it.',
  },
  eli5: {
    label: 'ELI5',
    description: 'Explain it as simply as you possibly can.',
  },
  scenario_application: {
    label: 'Scenario Application',
    description: 'Apply what you learned to a new, made-up situation.',
  },
  rapid_recall: {
    label: 'Rapid Recall',
    description: 'One quick, specific question. Low stakes.',
  },
};
