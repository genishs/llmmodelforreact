import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";

interface Props { mode?: string; }

function EgovAdminMemberEdit({ mode }: Props) {
  const navigate = useNavigate();
  const location = useLocation();

  const [idCheckStatus, setIdCheckStatus] = useState<{ checked: boolean; available: boolean; }>({ checked: false, available: false });
  const currentPath = location.pathname;

  let breadcrumbText = "사용자 관리";
  if (currentPath.includes('admin/members/create')) breadcrumbText = "사용자 등록";
  else if (currentPath.includes('admin/members/modify')) breadcrumbText = "사용자 수정";

  const [modeInfo, setModeInfo] = useState({ mode: mode ?? "", modeTitle: "", editURL: "" });
  const [memberDetail, setMemberDetail] = useState({});
  const [groupCodeOptions, setGroupCodeOptions] = useState<any[]>([]);
  const [deptCdOptions, setDeptCdOptions] = useState<any[]>([]);

  const initMode = () => {
    switch (mode) {
      case "create":
        setModeInfo({ mode: "create", modeTitle: "등록", editURL: "/members/insert" });
        break;
      case "modify":
        setModeInfo({ mode: "modify", modeTitle: "수정", editURL: `/members/update` });
        break;
      default:
        navigate({ pathname: "/error" }, { state: { msg: "" } });
    }
    retrieveDetail();
  };

  const retrieveDetail = () => {
    let retrieveDetailURL = "";
    if (mode === "create") {
      setMemberDetail({ tmplatId: "TMPLAT_MEMBER_DEFAULT", groupId: "GROUP_00000000000000000000", mberSttus: "P", checkIdResult: "중복ID를 체크해 주세요." });
      retrieveDetailURL = "/members/insert";
    } else if (mode === "modify") {
      retrieveDetailURL = `/members/update/${location.state?.uniqId}`;
    }
    const requestOptions = { method: "GET", headers: { "Content-type": "application/json" } };
    EgovNet.requestFetch(retrieveDetailURL, requestOptions, (resp) => {
      if (mode === "modify") setMemberDetail(resp.result.mberManageVO);
      groupCodeOptions = [];
      resp.result.groupId_result.forEach((item: any) => groupCodeOptions.push({ value: item.code, label: item.codeNm }));
      setGroupCodeOptions(groupCodeOptions);
      deptCdOptions = [];
      resp.result.deptList_result.forEach((item: any) => deptCdOptions.push({ value: item.code, label: item.codeNm }));
      setDeptCdOptions(deptCdOptions);
    });
  };

  const checkIdDplct = () => new Promise((resolve) => {
    const checkId = (memberDetail as any)["mberId"];
    if (!checkId) { setIdCheckStatus({ checked: false, available: false }); resolve(1); return; }
    const checkIdURL = `/etc/member_checkid/${checkId}`;
    const reqOptions = { method: "GET", headers: { "Content-type": "application/json" } };
    EgovNet.requestFetch(checkIdURL, reqOptions, (resp) => {
      if (resp.result.usedCnt > 0) { setMemberDetail({ ...memberDetail, checkIdResult: "이미 사용중인 아이디입니다." }); setIdCheckStatus({ checked: true, available: false }); resolve(resp.result.usedCnt); }
      else { setMemberDetail({ ...memberDetail, checkIdResult: "사용 가능한 아이디입니다." }); setIdCheckStatus({ checked: true, available: true }); resolve(0); }
    });
  });

  const formValidator = (formData: FormData) => new Promise<boolean>((resolve) => {
    if (!formData.get("mberId")) { alert("사용자 ID는 필수 값입니다."); return resolve(false); }
    if (!idCheckStatus.checked) { alert("아이디 중복 체크를 해주세요."); return resolve(false); }
    if (!idCheckStatus.available) { return resolve(false); }
    const password = formData.get("password");
    if (!password) { alert("암호는 필수 값입니다."); return resolve(false); }
    const reg = /^(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).{8,}$/;
    if (!reg.test(password)) { alert("비밀번호는 8자 이상이어야 하며, 숫자/영문자/특수문자를 모두 포함해야 합니다."); return resolve(false); }
    if (!formData.get("mberNm")) { alert("사용자 명은 필수 값입니다."); return resolve(false); }
    if (!formData.get("groupId")) { alert("권한 그룹은 필수 값입니다."); return resolve(false); }
    if (!formData.get("mberSttus")) { alert("사용자 상태값은 필수 값입니다."); return resolve(false); }
    if (!formData.get("deptCd")) { alert("부서 코드는 필수 값입니다."); return resolve(false); }
    resolve(true);
  });

  const updateMember = () => {
    const modeStr = mode === "create" ? "POST" : "PUT";
    let requestOptions = {};
    if (modeStr === "POST") {
      const formData = new FormData();
      for (let key in memberDetail) formData.append(key, (memberDetail as any)[key]);
      formValidator(formData).then((res) => {
        if (res) {
          requestOptions = { method: modeStr, headers: {}, body: formData };
          EgovNet.requestFetch(modeInfo.editURL, requestOptions, (resp) => {
            if (resp.resultCode === "RCV_SUCCESS") { alert("사용자 정보가 등록되었습니다."); navigate("/admin/members"); }
            else { navigate({ pathname: "/error" }, { state: { msg: resp.resultMessage } }); }
          });
        }
      });
    } else {
      if (formValidator(new FormData()).then((res) => res)) {
        requestOptions = { method: modeStr, headers: { "Content-type": "application/json" }, body: JSON.stringify(memberDetail) };
        EgovNet.requestFetch(modeInfo.editURL, requestOptions, (resp) => {
          if (resp.resultCode === "RCV_SUCCESS") navigate("/admin/members");
          else { navigate({ pathname: "/error" }, { state: { msg: resp.resultMessage } }); }
        });
      }
    }
  };

  useEffect(() => { initMode(); }, []);
  return <div>...</div>;
}

export default EgovAdminMemberEdit;