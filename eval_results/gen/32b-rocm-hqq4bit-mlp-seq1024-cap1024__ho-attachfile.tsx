import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface BoardFile {
  atchFileId: string;
  fileSn: string;
  orignlFileNm: string;
  fileMg: number;
}

interface Props {
  boardFiles?: BoardFile[];
  mode: string;
  fnChangeFile: (files: FileList | {}) => void;
  fnDeleteFile: (files: BoardFile[]) => void;
  posblAtchFileNumber?: number;
}

const EgovAttachFile: React.FC<Props> = ({
  boardFiles = [],
  mode,
  fnChangeFile,
  fnDeleteFile,
  posblAtchFileNumber = 1,
}) => {
  const navigate = useNavigate();

  const onClickDownFile = (atchFileId: string, fileSn: string) => {
    window.open(`${SERVER_URL}/file?atchFileId=${atchFileId}&fileSn=${fileSn}`);
  };

  const onClickDeleteFile = (atchFileId: string, fileSn: string, fileIndex: number) => {
    const requestOptions = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        atchFileId,
        fileSn,
      }),
    };

    fetch('/file', requestOptions)
      .then((response) => response.json())
      .then((data) => {
        if (Number(data.resultCode) === Number(CODE.RCV_SUCCESS)) {
          const updatedBoardFiles = [...boardFiles];
          updatedBoardFiles.splice(fileIndex, 1);
          fnDeleteFile(updatedBoardFiles);
          alert('첨부파일이 삭제되었습니다.');
          fnChangeFile({});
        } else {
          navigate(URL.ERROR, { state: { msg: data.resultMessage } });
        }
      })
      .catch((error) => {
        console.error(error);
      });
  };

  const onChangeFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if ((e.target.files?.length ?? 0) + boardFiles.length > posblAtchFileNumber) {
      alert(`총 첨부파일 개수는 ${posblAtchFileNumber}까지입니다.`);
      e.target.value = '';
      fnChangeFile({});
      return;
    }
    fnChangeFile(e.target.files ?? {});
  };

  const filesTag = boardFiles.map((item, index) => (
    <React.Fragment key={index}>
      <span>
        <a href="#LINK" onClick={(e) => { e.preventDefault(); onClickDownFile(item.atchFileId, item.fileSn); }} download>{item.orignlFileNm}</a>
        <span>[{item.fileMg}byte]</span>
      </span>
      {mode === CODE.MODE_MODIFY && (
        <button className="btn btn_delete" onClick={() => onClickDeleteFile(item.atchFileId, item.fileSn, index)}></button>
      )}
      <br />
    </React.Fragment>
  ));

  return (
    <dl>
      <dt>첨부파일</dt>
      <dd>
        <span className="file_attach">
          {filesTag}
          {mode === CODE.MODE_CREATE && (
            <>
              <input name="file_0" id="egovComFileUploader" type="file" multiple onChange={onChangeFileInput}></input>
              총 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber}개입니다.
            </>
          )}
          {mode === CODE.MODE_MODIFY && filesTag.length / 3 < posblAtchFileNumber && (
            <>
              <input name="file_0" id="egovComFileUploader" type="file" multiple onChange={onChangeFileInput}></input>
              현재 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber - filesTag.length / 3}개입니다.
            </>
          )}
        </span>
      </dd>
    </dl>
  );
};

export default EgovAttachFile;