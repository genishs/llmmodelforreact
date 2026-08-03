import React, { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";
import CODE from "@/constants/code";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovRadioButtonGroup from "@/components/EgovRadioButtonGroup";
import axios from "axios";
// import AdminNoticeCreatePopup from './AdminNoticeCreatePopup.jsx';

interface MemberDetail {
  mberId: string;
  password?: string; // 수정 시에만 필요함
  mberNm: string;
  groupId: string;
  deptCd: string;
  deptSubCd?: string;
  checkIdResult?: string;
}

interface ModeInfo {
  modeTitle: string;
  editURL: string;
}

function EgovAdminMemberEdit(props: { mode: number }) {
  console.group("EgovAdminMemberEdit");
  console.log("[Start] EgovAdminMemberEdit ------------------------------");
  console.log("EgovAdminMemberEdit [props] : ", props);

  const navigate = useNavigate();
  const location = useLocation();
  const checkRef = React.useRef<HTMLInputElement[]>([]);

  const [idCheckStatus, setIdCheckStatus] = useState({
    checked: false, // 중복 체크 버튼을 눌렀는지 여부
    available: false, // 체크 결과 사용 가능한지 여부
  });
  const currentPath = location.pathName;

  // URL 경로에 따라 표시할 텍스트 결정
  let breadcrumbText = "사용자 관리"; // 기본값 (등록/수정 둘 다 아닐 경우)

  if (currentPath.includes('admin/members/create')) {
    breadcrumbText = "사용자 등록";
  } else if (currentPath.includes('admin/members/modify')) {
    breadcrumbText = "사용자 수정";
  }

  //0918로그인가능여부수정?
  // console.log("EgovAdminMemberEdit [location] : ", location);
  const uniqId = location.state?.uniqId || "";
  const mberSttusRadioGroup = [
    { value: "P", label: "가능" },
    { value: "A", label: "대기" },
    { value: "D", label: "탈퇴" },
  ];
  //const groupCodeOptions = [{ value: "GROUP00000000000000", label: "ROLEADMIN" }, { value: "GROUP00000000000001", label: "ROLEUSER" }];
  //백엔드에서 보내온 값으로 변경(위 1줄 대신 아래 1줄 추가)
  let [groupCodeOptions, setGroupCodeOptions] = useState<{ value: string; label: string }[]>([]);
  const [