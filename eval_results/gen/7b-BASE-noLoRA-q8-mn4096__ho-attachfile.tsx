import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

import URL from "@/constants/url";
import * as EgovNet from "@/api/egovFetch";
import { SERVER_URL } from "@/config";
import CODE from "@/constants/code";

interface EgovAttachFileProps {
  boardFiles: any[];
  mode: string;
  fnChangeFile: (files: FileList | null) => void;
  fnDeleteFile: (boardFiles: any[]) => void;
  posblAtchFileNumber?: number;
}

function EgovAttachFile({
  boardFiles,
  mode,
  fnChangeFile,
  fnDeleteFile,
  posblAtchFileNumber = 1,
}: EgovAttachFileProps) {
  console.groupCollapsed("EgovAttachFile");

  const navigate = useNavigate();

  function onClickDownFile(atchFileId: string, fileSn: number) {
    window.open(
      SERVER_URL + "/.file?atchFileId=" + atchFileId + "&amp; fileSn=" + fileSn + ""
    );
  }

  function onClickDeleteFile(atchFileId: string, fileSn: number, fileIndex: number) {
    console.log("onClickDeleteFile Params : ", atchFileId, fileSn, fileIndex);

    const requestOptions = {
      method: "POST",
      headers: {
        "Content-type": "application/json",
      },
      body: JSON.stringify({
        atchFileId: atchFileId,
        fileSn: fileSn,
      }),
    };
    EgovNet.requestFetch(`/.file`, requestOptions, function (resp) {
      console.log("===>>> board file delete= ", resp);
      if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
        // 성공
        console.log("Deleted fileIndex = ", fileIndex);
        const _deleteFile = boardFiles.splice(fileIndex, 1);
        const _boardFiles = Object.assign([], boardFiles);
        fnDeleteFile(_boardFiles);
        alert("첨부파일이 삭제되었습니다.");
        fnChangeFile({});
      } else {
        navigate(
          { pathname: URL.ERROR },
          { state: { msg: resp.resultMessage } }
        );
      }
    });
  }

  function onChangeFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    console.log("===>>> e = " + e.target.files[0]);
    if (
      e.target.files.length + (boardFiles?.length || 0) >
      posblAtchFileNumber
    ) {
      alert("총 첨부파일 개수는 " + posblAtchFileNumber + " 까지 입니다.");
      e.target.value = null; // 파일 입력란 화면 초기화
      fnChangeFile(null); // 상위 컴포넌트의 저장된 값 초기화
      return false;
    }
    fnChangeFile(e.target.files);
  }

  let filesTag: React.ReactNode[] = [];

  if (boardFiles !== undefined) {
    boardFiles.forEach(function (item, index) {
      filesTag.push(
        <React.Fragment key={index}>
          <span>
            <a
              href={"#LINK"}
              onClick={(e) => {
                e.preventDefault();
                onClickDownFile(item.atchFileId, item.fileSn);
              }}
              download
            >
              {item.orignlFileNm}
            </a>
            <span>[{item.fileMg}byte]</span>
          </span>
        </React.Fragment>
      );

      if (mode === CODE.MODE_MODIFY) {
        filesTag.push(
          <React.Fragment key={["button", `${index}`].join(" ")}>
            <button
              className="btn btn_delete"
              onClick={() => {
                onClickDeleteFile(item.atchFileId, item.fileSn, index);
              }}
            ></button>
          </React.Fragment>
        );
      }
      filesTag.push(<br key={["br", `${index}`].join(" ")} />);
    });
  }
  console.log("filesTag : ", filesTag);
  console.groupEnd("EgovAttachFile");

  return (
    <dl>
      <dt className="title">첨부파일</dt>
      <dd>
        <span className="egovComFileUploader">
          {filesTag}
          {mode === CODE.MODE_CREATE && (
            <>
              <input
                name="egovComFileUploader"
                type="text"
                multiple
                onChange={(e) => onChangeFileInput(e)}
              ></input>
              총 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber} 개 입니다.
            </>
          )}
          {/* 첨부파일 1개 당  filesTag는 3개 요소(span, button, br)를 가진다 */}
          {mode === CODE.MODE_MODIFY &&
            filesTag.length / 3 < posblAtchFileNumber && (
              <>
                <input
                  name="egovComFileUploader"
                  type="text"
                  multiple
                  onChange={(e) => onChangeFileInput(e)}
                ></input>
                현재 업로드 가능한 첨부파일 개수는{" "}
                {posblAtchFileNumber - filesTag.length / 3} 개 입니다.
              </>
            )}
        </span>
      </dd>
    </dl>
  );
}

export default EgovAttachFile;