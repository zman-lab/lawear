import { Subject } from '../../../types';
import { files as hyungsoFiles } from './hyungso';
import { files as hyungFiles } from './hyung';
import { files as minsoFiles } from './minso';
import { files as minbeopFiles } from './minbeop';
import { files as budeungFiles } from './budeung';
import { files as budeungYegyuFiles } from './budeung_yegyu';

const allSubjectDefs: Subject[] = [
  {
    id: "hyungso_2026",
    name: "형사소송법 2026",
    shortName: "형소",
    colorClass: "rose",
    files: hyungsoFiles,
    totalQuestions: hyungsoFiles.reduce((sum, f) => sum + f.questions.length, 0),
    completedQuestions: 0,
  },
  {
    id: "hyung_2026",
    name: "형법 2026",
    shortName: "형법",
    colorClass: "orange",
    files: hyungFiles,
    totalQuestions: hyungFiles.reduce((sum, f) => sum + f.questions.length, 0),
    completedQuestions: 0,
  },
  {
    id: "minso_2026",
    name: "민사소송법 2026",
    shortName: "민소",
    colorClass: "blue",
    files: minsoFiles,
    totalQuestions: minsoFiles.reduce((sum, f) => sum + f.questions.length, 0),
    completedQuestions: 0,
  },
  {
    id: "minbeop_2026",
    name: "민법 2026",
    shortName: "민법",
    colorClass: "emerald",
    files: minbeopFiles,
    totalQuestions: minbeopFiles.reduce((sum, f) => sum + f.questions.length, 0),
    completedQuestions: 0,
  },
  {
    id: "budeung_2026",
    name: "부동산등기법 2026",
    shortName: "부등",
    colorClass: "purple",
    files: budeungFiles,
    totalQuestions: budeungFiles.reduce((sum, f) => sum + f.questions.length, 0),
    completedQuestions: 0,
  },
  {
    id: "budeung_yegyu_2026",
    name: "부동산등기법 예규 2026",
    shortName: "부등예규",
    colorClass: "violet",
    files: budeungYegyuFiles,
    totalQuestions: budeungYegyuFiles.reduce((sum, f) => sum + f.questions.length, 0),
    completedQuestions: 0,
  },
];

// files가 비어있는 과목은 제외
export const subjects2026: Subject[] = allSubjectDefs.filter(s => s.files.length > 0);
