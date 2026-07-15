import { Reducer, Dispatch } from 'react';

type Todo = { id: string; text: string; done: boolean };
enum ActT { ADD = 'add', REMOVE = 'remove', TOGGLE = 'toggle' }
interface AddAct { type: ActT.ADD; text: string; }
interface RemAct { type: ActT.REMOVE; id: string; }
interface TglAct { type: ActT.TOGGLE; id: string; }
export type TodoAct = AddAct | RemAct | TglAct;

function reducer(state: Todo[], act: TodoAct): Todo[] {
  switch (act.type) {
    case ActT.ADD: return [...state, { id: crypto.randomUUID(), text: act.text, done: false }];
    case ActT.REMOVE: return state.filter((t) => t.id !== act.id);
    case ActT.TOGGLE: return state.map((t) => (t.id === act.id ? { ...t, done: !t.done } : t));
    default: return state;
  }
}

export function useTodo(): [Todo[], Dispatch<TodoAct>] {
  const [todos, dispatch] = React.useReducer<Reducer<Todo[], TodoAct>>(reducer, []);
  return [todos, dispatch];
}