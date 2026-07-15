import React from "react";
import { useNavigate } from "react-router-dom";

import URL from "@/constants/url";
import * as EgovNet from "@/api/egovFetch";
import { SERVER_URL } from "@/config";
import CODE from "@/constants/code";

interface Props {
  boardFiles?: { [key: string]: any }[];
  mode: number;
  fnChangeFile: (files: FileList | null) => void;
  fnDeleteFile: (files: { [key: string]: any }[]) => void;
  posblAtchFileNumber?: number;
}

function EgovAttachFile({ boardFiles, mode, fnChangeFile, fnDeleteFile, posblAtchFileNumber }: Props): JSX.Element {
  console.groupCollapsed("EgovAttachFile");

  if (typeof posblAtchFileNumber == "undefined" || posblAtchFileNumber == null) {
    posblAtchFileNumber = 1;
  }

  const navigate = useNavigate();

  function onClickDownFile(atchFileId: string, fileSn: string): void {
    window.open(`${SERVER_URL}/file?atchFileId=${atchFileId}&fileSn=${fileSn}`);
  }

  function onClickDeleteFile(atchFileId: string, fileSn: string, fileIndex: number): void {
    console.log("onClickDeleteFile Params :", atchFileId, fileSn, fileIndex);

    const requestOptions = {
      method: "POST",
      headers: { "Content-type": "application/json" },
      body: JSON.stringify({ atchFileId, fileSn }),
    };

    EgovNet.requestFetch("/file", requestOptions, (resp: { resultCode: number; resultMessage: string }) => {
      console.log("===>>> board file delete=", resp);
      if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
        console.log("Deleted fileIndex =", fileIndex);
        const _deleteFile = boardFiles?.splice(fileIndex, 1);
        const _boardFiles = [...(boardFiles ?? [])];
        fnDeleteFile(_boardFiles);
        alert("첨부파일이 삭제되었습니다.");
        fnChangeFile(null);
      } else {
        navigate({ pathname: URL.ERROR }, { state: { msg: resp.resultMessage } });
      }
    });
  }

  function onChangeFileInput(e: React.ChangeEvent<HTMLInputElement>): void {
    console.log("===>>> e =", e.target.files);
    if (e.target.files && e.target.files.length + (boardFiles?.length ?? 0) > posblAtchFileNumber) {
      alert(`총 첨부파일 개수는 ${posblAtchFileNumber} 까지 입니다.`);
      e.target.value = "";
      fnChangeFile(null);
      return;
    }
    fnChangeFile(e.target.files);
  }

  let filesTag: JSX.Element[] = [];

  if (boardFiles) {
    boardFiles.forEach((item, index) => {
      filesTag.push(
        <React.Fragment key={index}>
          <span>
            <a href="#LINK" onClick={(e) => { e.preventDefault(); onClickDownFile(item.atchFileId, item.fileSn); }} download>{item.orignlFileNm}</a>
            <span>[{item.fileMg}byte]</span>
          </span>
        </React.Fragment>
      );

      if (mode === CODE.MODE_MODIFY) {
        filesTag.push(
          <React.Fragment key={`button-${index}`}>
            <button className="btn btn_delete" onClick={() => onClickDeleteFile(item.atchFileId, item.fileSn, index)}></button>
          </React.Fragment>
        );
      }
      filesTag.push(<br key={`br-${index}`} />);
    });
  }
  console.log("filesTag :", filesTag);
  console.groupEnd("EgovAttachFile");

  return (
    <dl>
      <dt>첨부파일</dt>
      <dd>
        <span className="file_attach">
          {filesTag}
          {mode === CODE.MODE_CREATE && (
            <>
              <input name="file_0" id="egovComFileUploader" type="file" multiple onChange={onChangeFileInput} />
              총 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber} 개 입니다.
            </>
          )}
          {mode === CODE.MODE_MODIFY && filesTag.length / 3 < posblAtchFileNumber && (
            <>
              <input name="file_0" id="egovComFileUploader" type="file" multiple onChange={onChangeFileInput} />
              현재 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber - Math.floor(filesTag.length / 3)} 개 입니다.
            </>
          )}
        </span>
      </dd>
    </dl>
  );
}

export default EgovAttachFile;