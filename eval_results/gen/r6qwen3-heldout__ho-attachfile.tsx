import React from 'react';
import { useNavigate } from 'react-router-dom';

interface FileItem { orignlFileNm: string; fileMg: number; atchFileId: string; fileSn: number; }
type ModeType = 'CREATE' | 'MODIFY'; // MODE_CREATE 또는 MODE_MODIFY

const CODE = { RCV_SUCCESS: 200, MODE_CREATE: 'CREATE', MODE_MODIFY: 'MODIFY' };

interface Props {
  boardFiles?: FileItem[];
  mode: ModeType;
  fnChangeFile: (files: FileList | {}) => void;
  fnDeleteFile: (updatedFiles: FileItem[]) => void;
  posblAtchFileNumber?: number;
}

async function requestFetch(url: string, options: RequestInit, cb: (r: any) => void): Promise<void> {
  try {
    const res = await fetch(url, options); const data = await res.json(); cb(data);
  } catch (err) { throw err; }
}

function EgovAttachFile({ boardFiles = [], mode, fnChangeFile, fnDeleteFile, posblAtchFileNumber }: Props) {
  const navigate = useNavigate();

  const [uploadCount, setUploadCount] = React.useState(boardFiles.length ?? 0);

  async function handleDownload(id: string, sn: number) {
    window.open(`${SERVER_URL}/file?atchFileId=${id}&fileSn=${sn}`);
  }

  async function handleDelete(id: string, sn: number, idx: number) {
    await requestFetch('/file', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ atchFileId: id, fileSn: sn }) }, (res) =>
      res.resultCode === String(CODE.RCV_SUCCESS)
        ? (() => { fnDeleteFile(boardFiles.filter((_, i) => i !== idx)); setUploadCount(uploadCount - 1); })(void 0)
        : navigate(URL.ERROR, { state: { msg: res.resultMessage } })
    );
  }

  const maxFiles =
    posblAtchFileNumber ?? ((mode === CODE.MODE_MODIFY ? uploadCount : 1) > 1 ? 999999 : 1);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files) return;
    if (e.target.files.length + uploadCount > maxFiles) {
      alert(`최대 ${maxFiles}개까지 가능합니다.`);
      e.target.value = ''; fnChangeFile(void 0); return;
    }
    fnChangeFile(e.target.files); setUploadCount((c) => c + e.target.files.length);
  }

  const fileList = boardFiles.map((f, i) => [
    <span key={`${i}-name`}><a href="#" onClick={(e) => { e.preventDefault(); handleDownload(f.atchFileId, f.fileSn); }}>{f.orignlFileNm}</a><span>[{f.fileMg}B]</span></span>,
    ...(mode === CODE.MODE_MODIFY ? [<button key={`${i}-del`} onClick={() => handleDelete(f.atchFileId, f.fileSn, i)}>삭제</button>] : []),
    <br key={`${i}-break`}],
  ).flat() as JSX.Element[];

  return (
    <dl style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <dt>첨부파일</dt>
      <dd style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        {fileList}
        {mode === CODE.MODE_CREATE && (<label htmlFor="egovComFileUploader">추가</label>)}
        <input id="egovComFileUploader" type="file" accept=".pdf,.docx,.xlsx,image/*" multiple onChange={handleChange} />
        {mode === CODE.MODE_MODIFY && uploadCount < maxFiles && (<label htmlFor="egovComFileUploader">추가 ({maxFiles - uploadCount}개 남음)</label>)}
      </dd>
    </dl>
  );
}

export default EgovAttachFile;