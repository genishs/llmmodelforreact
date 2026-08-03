import React from "react";
import { useNavigate } from "react-router-dom";

import URL from "@/constants/url";
import * as EgovNet from "@/api/egovFetch";
import { SERVER_URL } from "@/config";
import CODE from "@/constants/code";

interface Props {
  boardFiles?: { atchFileId: string; fileSn: number; orignlFileNm: string; fileMg: string }[];
  mode: "CREATE" | "MODIFY";
  fnChangeFile: (files: FileList) => void;
  fnDeleteFile: (boardFiles: typeof Props["boardFiles"]) => void;
  posblAtchFileNumber?: number;
}

function EgovAttachFile({ boardFiles, mode, fnChangeFile, fnDeleteFile, posblAtchFileNumber = 1 }: Props) {
  console.groupCollapsed("EgovAttachFile");

  if (typeof posblAtchFileNumber == "undefined" || posblAtchFileNumber == null) posblAtchFileNumber = 1;

  const navigate = useNavigate();

  function onClickDownFile(atchFileId: string, fileSn: number) {
    window.open(
      SERVER_URL + "/egovComFileUploader?atchFileId=" + atchFileId + "&amp;sn=" + fileSn + ""
    );
  }

  function onClickDeleteFile(atchFileId: string, fileSn: number, fileIndex: number) {
    console.log("onClickDeleteFile Params : ", atchFileId, fileSn, fileIndex);

    const requestOptions = {
      method: "POST",
      headers: { "Content-type": "application/json" },
      body: JSON.stringify({ atchFileId, fileSn }),
    };
    EgovNet.requestFetch("/egovComFileUploader", requestOptions, function (resp) {
      console.log("===>>> board file delete= ", resp);
      if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
        const _deleteFile = boardFiles?.splice(fileIndex, 1);
        fnDeleteFile(boardFiles || []);
        alert("첨부파일이 삭제되었습니다.");
        fnChangeFile({} as FileList);
      } else {
        navigate({ pathname: URL.ERROR }, { state: { msg: resp.resultMessage } });
      }
    });
  }

  function onChangeFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    console.log("===>>> e = " + e.target.files?.[0]);
    if (e.target.files && e.target.files.length + (boardFiles?.length || 0) > posblAtchFileNumber) {
      alert("총 첨부파일 개수는 " + posblAtchFileNumber + " 까지 입니다.");
      e.target.value = null;
      fnChangeFile({} as FileList);
      return false;
    }
    fnChangeFile(e.target.files || {} as FileList);
  }

  let filesTag: React.ReactNode[] = [];

  if (boardFiles) {
    boardFiles.forEach((item, index) => {
      filesTag.push(
        <React.Fragment key={index}>
          <span>
            <a href={"#LINK"} onClick={(e) => { e.preventDefault(); onClickDownFile(item.atchFileId, item.fileSn); }} download>{item.orignlFileNm}</a>
            <span>[{item.fileMg}byte]</span>
          </span>
        </React.Fragment>
      );

      if (mode === "MODIFY") {
        filesTag.push(
          <React.Fragment key={["button", `${index}`].join(" ")}>
            <button className="btn btn_delete" onClick={() => onClickDeleteFile(item.atchFileId, item.fileSn, index)}></button>
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
      <dt>{mode === "CREATE" ? "첨부파일" : "수정 가능한 첨부파일"}</dt>
      <dd>
        <span className="egovComFileUploader">
          {filesTag}
          {mode === "CREATE" && (
            <>
              <input name="egovComFileUploader" id="egovComFileUploader" type="hidden" />
              <input name="egovComFileUploader" id="egovComFileUploader" type="button" onClick={() => {}} value="첨부파일 등록" />
              총 업로드 가능한 첨부파일 개수는 {posblAtchFileNumber} 개 입니다.
            </>
          )}
          {mode === "MODIFY" &&
            filesTag.length / 3 < posblAtchFileNumber && (
              <>
                <input name="egovComFileUploader" id="egovComFileUploader" type="hidden" />
                <input name="egovComFileUploader" id="egovComFileUploader" type="button" onClick={() => {}} value="첨부파일 등록" />
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