/** A category: exactly `COLS` words that belong together. */
export type Group = {
	id: string;
	/** Revealed only once the row is cleared. */
	label: string;
	words: string[];
};

export type Puzzle = {
	id: string;
	name: string;
	/** BCP-47 tag. Everything is English for now; see DESIGN.md. */
	language: string;
	/** Exactly `ROWS` groups of `COLS` words. */
	groups: Group[];
};

/** A word on the board. Ids are stable for the life of a game so keyed each blocks work. */
export type Tile = {
	id: number;
	word: string;
	group: string;
};

export type Row = Tile[];

/** A cell on the board, top-left origin. */
export type Position = { row: number; col: number };

export type SolvedRow = {
	group: Group;
	/** Which check number cleared it, for the replay log. */
	check: number;
};

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
