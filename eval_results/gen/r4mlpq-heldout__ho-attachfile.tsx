interface Props {
  boardFiles?: BoardFile[];
  mode: number;
  fnChangeFile: (f: FileList | null) => void;
  fnDeleteFile: (b: BoardFile[]) => void;
  posblAtchFileNumber?: number;
}

function EgovAttachFile({ boardFiles, mode, fnChangeFile, fnDeleteFile, posblAtchFileNumber }: Props): JSX.Element { ... }