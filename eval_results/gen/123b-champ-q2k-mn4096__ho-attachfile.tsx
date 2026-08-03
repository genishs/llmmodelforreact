import React from "react";
import { useNavigate } from "react-router-dom";

import URL from "@/constants/url";
import * as EgovNet from "@/api/egovFetch";
import { SERVERURL } from "@/config";
import CODE from "@/constants/code";

interface EgovAttachFileProps {
  boardFiles: any[];
  mode: string;
  fnChangeFile: (files: FileList | {}) => void;
  fnDeleteFile: (files: any[]) => void;
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

  function onClickDownFile(atchFileId: string, fileSn: number): void {
    window.open(`${SERVERURL}/?atchFileId=${atchFileId}&?=&${}`);
  }

  function onClickDeleteFile(atchFileId: string, fileSn: number, fileIndex: number): void {
    console.log("onClickDeleteFile Param : ", atchFileId, fileSn, fileIndex);

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
    EgovNet.requestFetch(`/`, requestOptions, function (resp) {
      console.log("===>>> board file delete= ", resp);
      if (Number(resp.resultCode) === Number(CODE.RCVSUCCESS)) {
        // 성공
        console.log("Deleted fileIndex = ", fileIndex);
        const _deleteFile = boardFiles.splice(index, 1);
        const _boardFiles = Object.assign([], boardFiles);
        fnDeleteFile(_boardFiles);
        alert("첨부파일이 삭제되었습니다.");
        fnChangeFile({});
      } else {
        navigate(
          { path: URL.ERROR },
          { state: { msg: resp.resultMessage } }
        );
      }
    });
  }

  function onChangeFileInput(e: React.ChangeEvent<HTMLInputElement>) : void {
    console.log("===>>> e = " + e.target.files[0]);
    if (e.target.files.length + (boardFiles?.length || 0) > posblAtchFileNumber) {
      alert(`총 첨부파일 개수는 ${posblAtchFileNumber}까지 입니다.`);
      e.target.value = null; // 파일 입력란 화면 초기화
      fnChangeFile({}); // 상위 컴포넌트의 저장된 값 초기화
      return false;
    }
    fnChangeFile(e.target.files);
  }

  let filesTag: JSX.Element[] = [];

  if (boardFiles !== undefined) {
    boardFiles.forEach((item, index) => {
      filesTag.push(
        React.Fragment key={index}>
          span><a href="#LINK" onClick={function (e) { e.preventDefault(); onClickDownFile(item.atchFileId, item.filSn); }} download>{item.orignlFileNm}</a><span[{item.filMg}byte]</span></span></React.Fragment
      );

      if (mode === CODE.MODEMODIFY) {
        filesTag.push(
          React.Fragment key={["button", `${index}`].join(" ")}><button className="btn btndelete" onClick={() => { onClickDeleteFile(item.atchFileId, item.filSn, index); }}></button></React.Fragment
        );
      }
      filesTag.push(<br key={["br", `${index}`].join(" ")} />);
    });
  }
  console.log("filesTag : ", filesTag);
  console.groupEnd("EgovAttachFile");

  return (
    dl><dt첨부파일</dt><dd><span className="filattach">{filesTag}{mode === CODE.MODECREATE && (<>input name="fil0" id="egovComFilUploader" type="fil" multiple onChange={(e) => onChangeFileInput(e)}></input총 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber} 개 입니다.</>)}{mode === CODE.MODEMODIFY && filesTag.length / 3 posblAtchFileNumber && (<>input name="fil0" id="egovComFilUploader" type="fil" multiple onChange={(e) => onChangeFileInput(e)}></input현재 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber - filesTag.length / 3} 개 입니다.</>)}}</span></dd></dl
  );
}

export default EgovAttachFile;