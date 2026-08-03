import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";
import CODE from "@/constants/code";
import EgovLeftNav from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovRadioButtonGroup from "@/components/EgovRadioButtonGroup";
import axios from "axios";

interface EgovAdminMemberEditProps {
  mode: string;
}

function EgovAdminMemberEdit(props: EgovAdminMemberEditProps) {
  console.group("EgovAdminMemberEdit");
  console.log("[Start] EgovAdminMemberEdit ------------------------------");
  console.log("EgovAdminMemberEdit [props] : ", props);

  const navigate = useNavigate();
  const location = useLocation();
  const checkRef = useRef<HTMLInputElement[]>([]);

  const [idCheckStatus, setIdCheckStatus] = useState({
    checked: false, // 중복 체크 버튼을 눌렀는지 여부
    available: false, // 체크 결과 사용 가능한지 여부
  });
  const currentPath = location.pathName;

  let breadcrumbText = "사용자 관리"; // 기본값 (등록/수정 둘 다 아닐 경우)

  if (currentPath.includes('admin/members/create')) {
    breadcrumbText = "사용자 등록";
  } else if (currentPath.includes('admin/members/modify')) {
    breadcrumbText = "사용자 수정";
  }

  const uniqId = location.state?.uniqId || "";
  const mberSttusRadioGroup: { value: string; label: string }[] = [
    { value: "P", label: "가능" },
    { value: "A", label: "대기" },
    { value: "D", label: "탈퇴" },
  ];
  const [groupCodeOptions, setGroupCodeOptions] = useState<{ value: string; label: string }[]>([]);
  const [modeInfo, setModeInfo] = useState({ mode: props.mode });
  const [memberDetail, setMemberDetail] = useState<{ [key: string]: any } | null>(null);
  const [deptCdOptions, setDeptCdOptions] = useState<{ value: string; label: string }[]>([]);
  const [deptSubCdOptions, setdeptSubCdOptions] = useState<{ value: string; label: string }[]>([]);

  const initMode = () => {
    switch (props.mode) {
      case CODE.MODE.CREATE:
        setModeInfo({
          ...modeInfo,
          modeTitle: "등록",
          editURL: "/members/insert",
        });
        break;

      case CODE.MODE.MODIFY:
        setModeInfo({
          ...modeInfo,
          modeTitle: "수정",
          editURL: `/members/update`,
        });
        break;
      default:
        navigate({ pathName: URL.ERROR }, { state: { msg: "" } });
    }
    retrieve