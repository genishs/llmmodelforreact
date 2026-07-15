import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";
import CODE from "@/constants/code";
import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovRadioButtonGroup from "@/components/EgovRadioButtonGroup";
import axios from "axios";

interface IdCheckStatus {
  checked: boolean;
  available: boolean;
}

interface ModeInfo {
  mode: string;
  modeTitle?: string;
  editURL?: string;
}

interface MemberDetail {
  tmplatId?: string;
  groupId?: string;
  mberSttus?: string;
  checkIdResult?: string;
  deptCd?: string;
  deptSubCd?: string;
}

function EgovAdminMemberEdit({ mode }: { mode: string }) {
  const navigate = useNavigate();
  const location = useLocation();
  const checkRef = useRef<[HTMLInputElement | null, HTMLInputElement | null, HTMLInputElement | null]>([null, null, null]);

  const [idCheckStatus, setIdCheckStatus] = useState<IdCheckStatus>({ checked: false, available: false });
  const [modeInfo, setModeInfo] = useState<ModeInfo>({ mode });
  const [memberDetail, setMemberDetail] = useState<MemberDetail>({});
  const [groupCodeOptions, setGroupCodeOptions] = useState<{ value: string; label: string }[]>([]);
  const [deptCdOptions, setDeptCdOptions] = useState<{ value: string; label: string }[]>([]);
  const [deptSubCdOptions, setdeptSubCdOptions] = useState<{ value: string; label: string }[]>([]);

  const initMode = () => {
    switch (mode) {
      case CODE.MODE_CREATE:
        setModeInfo({ ...modeInfo, modeTitle: "등록", editURL: "/members/insert" });
        break;
      case CODE.MODE_MODIFY:
        setModeInfo({ ...modeInfo, modeTitle: "수정", editURL: `/members/update` });
        break;
      default:
        navigate({ pathname: URL.ERROR }, { state: { msg: "" } });
    }
    retrieveDetail();
  };

  const retrieveDetail = () => {
    let retrieveDetailURL = "";
    if (modeInfo.mode === CODE.MODE_CREATE) {
      setMemberDetail({
        tmplatId: "TMPLAT_MEMBER_DEFAULT",
        groupId: "GROUP_00000000000000000000",
        mberSttus: "P",
        checkIdResult: "중복ID를 체크해 주세요.",
        deptCd: "5080001"
      });
      retrieveDetailURL = `/members/insert`;
    } else if (modeInfo.mode === CODE.MODE_MODIFY) {
      retrieveDetailURL = `/members/update/${location.state?.uniqId}`;
    }
    const requestOptions = { method: "GET", headers: { "Content-type": "application/json" } };
    const fetchSubDept = async (deptCd: string, currentSubCd?: string) => {
      try {
        const resp = await axios.get("/geoportal/api/api/deptSubList", { params: { deptCd }, withCredentials: true });
        const subOptions = (resp.data.deptSubList_result || []).map(item => ({ value: item.code, label: item.codeNm }));
        setdeptSubCdOptions(subOptions);
        if (currentSubCd && subOptions.some(opt => opt.value === currentSubCd)) {
          setMemberDetail(prev => ({ ...prev, deptSubCd: currentSubCd }));
        } else {
          setMemberDetail(prev => ({ ...prev, deptSubCd: "" }));
        }
      } catch (error) { console.error("하위 부서 목록 불러오기 실패", error); }
    };
    EgovNet.requestFetch(retrieveDetailURL, requestOptions, (resp) => {
      if (modeInfo.mode === CODE.MODE_MODIFY) {
        setMemberDetail(resp.result.mberManageVO);
        if (resp.result.mberManageVO.deptCd) fetchSubDept(resp.result.mberManageVO.deptCd, resp.result.mberManageVO.deptSubCd);
      }
      groupCodeOptions = [];
      resp.result.groupId_result.forEach((item) => groupCodeOptions.push({ value: item.code, label: item.codeNm }));
      setGroupCodeOptions(groupCodeOptions);
      const deptOptions = (resp.result.deptList_result || []).map(item => ({ value: item.code, label: item.codeNm }));
      const adminDeptOption = { value: '0000000', label: '관리자' }; deptOptions.unshift(adminDeptOption);
      setDeptCdOptions(deptOptions);
      setdeptSubCdOptions((resp.result.deptSubList_result || []).map(item => ({ value: item.code, label: item.codeNm })));
    });
  };

  const checkIdDplct = () => new Promise<number>((resolve) => {
    const checkId = memberDetail["mberId"];
    if (!checkId) { setIdCheckStatus({ checked: false, available: false }); resolve(1); return; }
    if (checkId.length < 5) { setIdCheckStatus({ checked: false, available: false }); resolve(-1); return; }
    const checkIdURL = `/etc/member_checkid/${checkId}`;
    const reqOptions = { method: "GET", headers: { "Content-type": "application/json" } };
    EgovNet.requestFetch(checkIdURL, reqOptions, (resp) => {
      if (resp.result.usedCnt > 0) { setMemberDetail({...memberDetail, checkIdResult: "이미 사용중인 아이디입니다."}); resolve(resp.result.usedCnt); setIdCheckStatus({ checked: true, available: false }); }
      else { setMemberDetail({...memberDetail, checkIdResult: "사용 가능한 아이디입니다."}); resolve(0); setIdCheckStatus({ checked: true, available: true }); }
    });
  });

  const formValidator = (formData: FormData) => new Promise<boolean>((resolve) => {
    if (!formData.get("mberId")) { alert("사용자 ID는 필수 값입니다."); return resolve(false); }
    if (!idCheckStatus.checked) { alert("아이디 중복 체크를 해주세요."); return resolve(false); }
    if (!idCheckStatus.available) { return resolve(false); }
    const password = formData.get("password");
    if (!password) { alert("암호는 필수 값입니다."); return resolve(false); }
    const reg = /^(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).{8,}$/;
    if (!reg.test(password)) { alert("비밀번호는 8자 이상이어야 하며, 숫자/영문자/특수문자를 모두 포함해야 합니다."); checkRef.current[1].value = ""; return resolve(false); }
    if (!formData.get("mberNm")) { alert("사용자 명은 필수 값입니다."); return resolve(false); }
    if (!formData.get("groupId")) { alert("권한 그룹은 필수 값입니다."); return resolve(false); }
    if (!formData.get("mberSttus")) { alert("사용자 상태값은 필수 값입니다."); return resolve(false); }
    if (!formData.get("deptCd")) { alert("부서 코드는 필수 값입니다."); return resolve(false); }
    resolve(true);
  });

  const updateMember = () => {
    const modeStr = mode === CODE.MODE_CREATE ? "POST" : "PUT";
    let requestOptions = {};
    if (modeStr === "POST") {
      const formData = new FormData(); Object.entries(memberDetail).forEach(([key, val]) => formData.append(key, String(val)));
      formValidator(formData).then(res => res && ((requestOptions = { method: modeStr, headers: {}, body: formData }), EgovNet.requestFetch(modeInfo.editURL, requestOptions, (resp) => { if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) { alert("사용자 정보가 등록되었습니다."); navigate(URL.ADMIN_MEMBERS); } else { navigate({ pathname: URL.ERROR }, { state: { msg: resp.resultMessage } }); } })));
    } else {
      if (formObjValidator()) { requestOptions = { method: modeStr, headers: { "Content-type": "application/json" }, body: JSON.stringify(memberDetail) }; EgovNet.requestFetch(modeInfo.editURL, requestOptions, (resp) => { if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) navigate(URL.ADMIN_MEMBERS); else navigate({ pathname: URL.ERROR }, { state: { msg: resp.resultMessage } }); }); }
    }
  };

  const deleteMember = (uniqId: string) => { const deleteMemberURL = `/members/delete/${uniqId}; const requestOptions = { method: "DELETE", headers: { "Content-type": "application/json" } }; EgovNet.requestFetch(deleteMemberURL, requestOptions, (resp) => { if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) { alert("사용자가 삭제되었습니다."); navigate(URL.ADMIN_MEMBERS); } else alert("ERR : " + resp.resultMessage); }); };

  useEffect(() => { if (memberDetail.deptCd) { const fetchSubDept = async () => { const resp = await axios.get("/geoportal/api/api/deptSubList", { params: { deptCd: memberDetail.deptCd }, withCredentials: true }); setdeptSubCdOptions((resp.data.deptSubList_result || []).map(item => ({ value: item.code, label: item.codeNm }))); if (memberDetail.deptSubCd && !deptSubCdOptions.some(opt => opt.value === memberDetail.deptSubCd)) setMemberDetail(prev => ({ ...prev, deptSubCd: "" })); }; fetchSubDept(); } }, [memberDetail.deptCd]);
  useEffect(() => { initMode(); }, []);

  return (
    <div className="new_wrap2" id="warp2"><div className="w100 d_flex d_jcc"><div className="w1200"><div className="nav_wrap d_flex d_end"><div className="nav d_flex d_end"><Link to={URL.MAIN}><div className="nav_ico img_all"></div></Link><div className="nav_ico_arr img_all"></div><Link to={URL.ADMIN}><div className="nav_txt">시스템 운영관리</div></Link><div className="nav_ico_arr img_all"></div><Link><div className="nav_txt">{modeInfo.mode === CODE.MODE_CREATE ? '사용자 등록' : '사용자 수정'}</div></Link></div></div></div><div className="con_wrap d_flex d_jcc"><div className="join"><h1 className="txt_cen join_h1">{modeInfo.mode === CODE.MODE_CREATE ? '사용자 등록' : '사용자 수정'}</h1><div className="join_txt_s">본 작성항목은 모두 필수 항목입니다.</div><div className="blue_line"></div><div className="join_box d_flex aic"><label htmlFor="user_id">사용자 ID<span>*</span></label>{modeInfo.mode === CODE.MODE_CREATE ? (<><input type="text" id="user_id" className="join_ser1" name="mberId" placeholder="사용자 ID는 5글자 이상 입력 해 주세요." defaultValue={memberDetail.mberId} onChange={(e) => setMemberDetail({ ...memberDetail, mberId: e.target.value })} /><div className="grey_btn" onClick={() => checkIdDplct()}>중복 ID 체크</div></>) : (<><input type="text" id="user_id" className="join_ser2" name="mberId" readOnly defaultValue={memberDetail.mberId} ref={(el) => checkRef.current[0] = el} required /></>)}</div><div className="join_box d_flex aic"><label htmlFor="user_pass">사용자 패스워드<span>*</span></label>{modeInfo.mode === CODE.MODE_CREATE ? (<><input type="password" id="user_pass" name="password" className="join_ser2" placeholder="8자리 이상 영문, 숫자, 특수문자를 포함해 주세요." defaultValue={memberDetail.password} onChange={(e) => setMemberDetail({ ...memberDetail, password: e.target.value })} ref={(el) => checkRef.current[1] = el} required /></>) : (<><input type="password" id="user_pass" className="join_ser2" name="password" onChange={(e) => setMemberDetail({ ...memberDetail, password: e.target.value })} ref={(el) => checkRef.current[1] = el} placeholder="8자리이상 영문, 숫자, 특수문자를 포함 해 주세요." /></>)}</div><div className="join_box d_flex aic"><label htmlFor="user_name2">사용자 명<span>*</span></label><input type="text" id="user_name2" name="mberNm" className="join_ser2" defaultValue={memberDetail.mberNm} onChange={(e) => setMemberDetail({ ...memberDetail, mberNm: e.target.value })} ref={(el) => checkRef.current[2] = el} required /></div><div className="join_box d_flex aic"><label htmlFor="groupId">사용자 권한<span>*</span></label><select id="groupId" name="groupId" title="회원권한유형선택" className="join_ser3" onChange={(e) => setMemberDetail({ ...memberDetail, groupId: e.target.value })} value={memberDetail.groupId}>{groupCodeOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div><div className="join_box d_flex aic"><label htmlFor="deptCd">소속 부서<span>*</span></label><select id="deptCd" name="deptCd" title="소속 부서 선택" className="join_ser4" onChange={async (e) => { const selectedDept = e.target.value; setMemberDetail({ ...memberDetail, deptCd: selectedDept }); try { const resp = await axios.get("/geoportal/api/api/deptSubList", { params: { deptCd: e.target.value }, withCredentials: true }); let deptSubCdOptions = []; (resp.data.deptSubList_result || []).forEach(item => deptSubCdOptions.push({ value: item.code, label: item.codeNm })); setdeptSubCdOptions(deptSubCdOptions); } catch (error) { console.error("하위 부서 목록 불러오기 실패", error); } }} value={memberDetail.deptCd}>{deptCdOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select><div className="mr20"></div>{deptSubCdOptions.length > 0 && <select className="join_ser4" id="deptSubCd" name="deptSubCd" value={memberDetail.deptSubCd} onChange={(e) => setMemberDetail({ ...memberDetail, deptSubCd: e.target.value })}><option>하위 부서 선택</option>{deptSubCdOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select>}</div><div className="grey_line"></div><div className="pop_btn_wrap"><div className="blu_btn" onClick={updateMember}>저 장</div>{modeInfo.mode === CODE.MODE_MODIFY && <div className="blu_btn" onClick={() => deleteMember(memberDetail.uniqId)}>삭 제</div>}<Link to={URL.ADMIN_MEMBERS}><div className="w_btn">목 록</div></Link></div></div></div></div><div className="c_wrap"><div className="location"></div></div>
  );
}

export default EgovAdminMemberEdit;