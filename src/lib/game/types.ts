/** One word of a category, and what puts it there. */
export type WordNote = {
	/** Carries its own word rather than riding on position, so a note cannot slide. */
	word: string;
	note: string;
};

/**
 * A category, written out.
 *
 * Players finish a board and go and look the row up — which category that was, what a
 * BASSET is, why CARDIGAN counts as a name. This is that search, answered in place.
 *
 * It travels on `Group`, which means it is revealed by exactly the rule the label is:
 * only a row that is on the table has one. Boards written before this existed have none,
 * and their rows simply do not open.
 */
export type Notes = {
	/** One sentence on what the category is. */
	summary: string;
	/** One line per word, in the order the category lists them. */
	words: WordNote[];
};

/** A category: exactly `COLS` words that belong together. */
export type Group = {
	id: string;
	/** Revealed only once the row is cleared. */
	label: string;
	words: string[];
	/** Revealed with the label, and read after it. Absent on boards written before notes. */
	notes?: Notes;
};

export type Puzzle = {
	id: string;
	name: string;
	/** BCP-47 tag. Everything is English for now; see DESIGN.md. */
	language: string;
	/** Exactly `ROWS` groups of `COLS` words. */
	groups: Group[];
};

/**
 * How a board landed. Three answers because a fourth costs more than it earns: the screen
 * asking has to be answerable in one tap by someone who wants to be playing.
 */
export type Difficulty = 'easy' | 'right' | 'hard';

/** A puzzle as a player may see it: which board this is, never what is on it. */
export type PuzzleMeta = Pick<Puzzle, 'id' | 'name' | 'language'>;

/** A word on the board. Ids are stable for the life of a game so keyed each blocks work. */
export type Tile = {
	id: number;
	word: string;
};

/**
 * Tile id to group id: the answer key, kept beside the board rather than on it.
 *
 * It used to ride on every tile, which meant a board and its solution were the same
 * object — there was no way to hand a player one without the other. A row is now just
 * tiles, and only whoever holds this map can say whether one is complete, which is what
 * lets the check live somewhere the player cannot read.
 */
export type Answer = Map<number, string>;

export type Row = Tile[];

/** A cell on the board, top-left origin. */
export type Position = { row: number; col: number };

export type SolvedRow = {
	group: Group;
	/** Which check number cleared it, for the replay log. */
	check: number;
	/** Position within its clearing batch, so a multi-row clear lands in sequence. */
	order: number;
};

/** A dealt board with nothing attached that grades it. Safe to hand to a player. */
export type Board = {
	puzzle: PuzzleMeta;
	rows: Row[];
};

/**
 * What a graded check tells the player: how many rows are right, which ones cleared, and
 * — only once the run is over — what was never found. Pin 4: it never says *where*.
 */
export type CheckOutcome = {
	/** Leading run of correct rows from the top: the rows that actually cleared. */
	locked: number;
	/** How many rows were correct anywhere. Never says which. */
	correctCount: number;
	/** The categories that cleared, top-first. The only answers a run gives up early. */
	cleared: Group[];
	/** Categories never found. Empty until the run is over, so a miss reveals nothing. */
	missed: Group[];
};

/**
 * Grades an arrangement. The seam the answer key sits behind: a session knows how to ask
 * and nothing about who answers, so the same game plays against a local key or a remote
 * one without noticing the difference.
 */
export type Checker = (rows: Row[], checksUsed: number) => Promise<CheckOutcome>;

/** The engine's own grading result, over rows it can see the key for. */
export type CheckResult = {
	/** Per-row, top-first, over the rows that were still in play. */
	correct: boolean[];
	/** Leading run of correct rows from the top — the rows that actually clear. */
	locked: number;
	/** How many rows were correct anywhere. Never says which. */
	correctCount: number;
	/** A check that clears nothing costs a life. */
	costLife: boolean;
};
