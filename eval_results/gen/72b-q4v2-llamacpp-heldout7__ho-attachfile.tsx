import React from "react";
import { useNavigate } from "react-router-dom";

import URL from "@/constants/url";
import * as EgovNet from "@/api/egovFetch";
import { SERVER_URL } from "@/config";
import CODE from "@/constants/code";

interface IEgovAttachFileProps {
  boardFiles: Array<{ atchFileId: string; fileSn: number; orignlFileNm: string; fileMg: number }>;
  mode: string;
  fnChangeFile: (files: FileList | {}) => void;
  fnDeleteFile: (boardFiles: Array<{ atchFileId: string; fileSn: number; orignlFileNm: string; fileMg: number }>) => void;
  posblAtchFileNumber?: number;
}

function EgovAttachFile({
  boardFiles,
  mode,
  fnChangeFile,
  fnDeleteFile,
  posblAtchFileNumber = 1
}: IEgovAttachFileProps) {
  console.groupCollapsed("EgovAttachFile");

  const navigate = useNavigate();

  function onClickDownFile(atchFileId: string, fileSn: number): void {
    window.open(
      `${SERVER_URL}/?atchFileId=${atchFileId}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}&amp;${"amp;" + "amp;"}