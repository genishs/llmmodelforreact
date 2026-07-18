import React from 'react';

interface Props {
  boardFiles?: Array<{ atchFileId: string; fileSn: number; orignlFileNm: string; fileMg: number }>;
  mode: string;
  fnChangeFile: (files: Array<File>) => void;
  fnDeleteFile: (files: Array<{ atchFileId: string; fileSn: number }>) => void;
  posblAtchFileNumber?: number;
}

function EgovAttachFile({ boardFiles, mode, fnChangeFile, fnDeleteFile, posblAtchFileNumber = 1 }: Props) {
  console.groupCollapsed('EgovAttachFile');

  const navigate = useNavigate();

  function onClickDownFile(atchFileId: string, fileSn: number) {
    window.open(SERVER_URL + '/file?atchFileId=' + atchFileId + '&fileSn=' + fileSn + '');
  }

  function onClickDeleteFile(atchFileId: string, fileSn: number, fileIndex: number) {
    console.log('onClickDeleteFile Params : ', atchFileId, fileSn, fileIndex);

    const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ atchFileId, fileSn }),
    };
    fetch('/file', requestOptions).then((res) => {
      if (!res.ok) throw new Error(res.statusText);
      const data = await res.json();
      if (data.resultCode === CODE.RCV_SUCCESS) {
        alert('첨부파일이 삭제되었습니다.');
        const updatedBoardFiles = [...boardFiles];
        updatedBoardFiles.splice(fileIndex, 1);
        fnDeleteFile(updatedBoardFiles);
      } else {
        alert('첨부파일 삭제 실패: ' + data.resultMessage);
      }
    }).catch((err) => console.error(err));
  }

  function onChangeFileInput(e: Event) {
    const files = Array.from(e.target.files);
    if ((boardFiles?.length ?? 0) + files.length > posblAtchFileNumber) {
      alert('총 첨부파일 개수는 ' + posblAtchFileNumber + ' 까지 입니다.');
      e.target.value = '';
      fnChangeFile([]);
      return;
    }
    fnChangeFile(files);
  }

  let filesTag = [];
  if (boardFiles) {
    for (let i = 0; i < boardFiles.length; i++) {
      filesTag.push(
        <li key={i}>
          <a href="#LINK" onClick={() => onClickDownFile(boardFiles[i].atchFileId, boardFiles[i].fileSn)}>{boardFiles[i].orignlFileNm}</a>
          <span>[{boardFiles[i].fileMg}byte]</span>
          {mode === 'modify' && <button onClick={() => onClickDeleteFile(boardFiles[i].atchFileId, boardFiles[i].fileSn, i)}>삭제</button>}
        </li>
      );
    }
  }

  return (
    <dl>
      <dt>첨부파일</dt>
      <dd>
        <ul>{filesTag}</ul>
        {mode === 'create' && <input name="file_0" id="egovComFileUploader" type="file" multiple onChange={onChangeFileInput} />}
        현재 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber - (boardFiles?.length ?? 0)} 개 입니다.
      </dd>
    </dl>
  );
}