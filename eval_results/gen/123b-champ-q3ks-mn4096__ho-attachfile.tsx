import React from "react";
import { useNavigate } from "react-router-dom";

import URL from "@/constants/url";
import * as EgovNet from "@/api/egovFetch";
import { SERVERURL } from "@/config";
import CODE from "@/constants/code";

interface EgovAttachFileProps {
  boardFiles: any[];
  mode: string;
  fnChangeFile: (files: FileList) => void;
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

  function onClickDownFile(atchFileId: string, fileSn: number): void {
    window.open(`${SERVERURL}/files?atchFileId=${atchFileId}&filesn=${filesn}`);
  }

  function onClickDeleteFile(atchFileId: string, fileSn: number, fileIndex: number): void {
    console.log("onClickDeleteFile Param:", atchFileId, fileSn, fileIndex);

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
    EgovNet.requestFetch(`/files`, requestOptions, (resp: any) => {
      console.log("===>>> board file delete=", resp);
      if (Number(resp.resultCode) === Number(CODE.RCVSUCCESS)) {
        // 성공
        console.log("Deleted fileIndex =", fileIndex);
        const _deleteFile = boardFiles.splice(filesIndex, 1);
        const _boardFiles = Object.assign([], boardFiles);
        fnDeleteFile(_boardFiles);
        alert("첨부파일이 삭제되었습니다.");
        fnChangeFile({});
      } else {
        navigate(URL.ERROR, { state: { msg: resp.resultMessage } });
      }
    });
  }

  function onChangeFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    console.log("===>>> e =", e.target.files?.[0]);
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
        React.createElement("span", { key: `span-${index}` }, [
          React.createElement("a", {
            href: "#LINK",
            onClick: (e: React.MouseEvent<HTMLAnchorElement>) => {
              e.preventDefault();
              onClickDownFile(item.atchFileId, item.filesn);
            },
            download: true,
          }, item.orignlFileNm),
          `[${item.filesMg}byte]`,
        ])
      );

      if (mode === CODE.MODEMODIFY) {
        filesTag.push(
          React.createElement("button", {
            className: "btn btn-delete",
            key: `button-${index}`,
            onClick: () => onClickDeleteFile(item.atchFileId, item.filesn, index),
          })
        );
      }
      filesTag.push(React.createElement("br", { key: `br-${index}` }));
    });
  }
  console.log("filesTag:", filesTag);
  console.groupEnd("EgovAttachFile");

  return (
    React.createElement("dl", null, [
      React.createElement("dt", null, "첨부파일"),
      React.createElement(
        "dd",
        null,
        React.createElement("span", { className: "files-attach" }, [
          ...filesTag,
          mode === CODE.MODECREATE && (
            React.createElement("input", {
              name: "files-0",
              id: "egovComFilesUploader",
              type: "files",
              multiple: true,
              onChange: onChangeFileInput,
            })
          ),
        ])
      ),
    ])
  );
}

export default EgovAttachFile;