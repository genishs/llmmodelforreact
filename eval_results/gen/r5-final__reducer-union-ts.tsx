export type TodoAction =
  | { type: "ADD"; text: string }
  | { type: "REMOVE"; id: number }
  | { type: "TOGGLE"; id: number };

export interface Todo {
  id: number;
  text: string;
  done: boolean;
}

function reducer(state: Todo[], action: TodoAction): Todo[] {
  switch (action.type) {
    case "ADD":
      return [...state, { id: Date.now(), text: action.text, done: false }];
    case "REMOVE":
      return state.filter((t) => t.id !== action.id);
    case "TOGGLE":
      return state.map((t) =>
        t.id === action.id ? { ...t, done: !t.done } : t
      );
    default:
      return state;
  }
}