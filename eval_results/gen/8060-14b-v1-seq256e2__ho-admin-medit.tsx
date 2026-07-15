import { useState, useEffect, useRef } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";

import * as EgovNet from "@/api/egovFetch";
import URL from "@/constants/url";
import CODE from "@/constants/code";

import { default as EgovLeftNav } from "@/components/leftmenu/EgovLeftNavAdmin";
import EgovRadioButtonGroup from "@/components/EgovRadioButtonGroup";
import axios from "axios";

interface Props {
  mode: string;
}

interface MemberDetail {
  tmplatId?: string;
  groupId?: string;
  mberSttus?: string;
  checkIdResult?: string;
  deptCd?: string;
  deptSubCd?: string;
  mberId?: string;
  password?: string;
  mberNm?: string;
  uniqId?: string;
}

interface IdCheckStatus {
  checked: boolean;
  available: boolean;
}

interface ModeInfo {
  mode: string;
  modeTitle?: string;
  editURL?: string;
}

interface Option {
  value: string;
  label: string;
}

function EgovAdminMemberEdit({ mode }: Props) {
  console.group("EgovAdminMemberEdit");
  console.log("[Start] EgovAdminMemberEdit ------------------------------");
  console.log("EgovAdminMemberEdit [props] : ", { mode });

  const navigate = useNavigate();
  const location = useLocation();
  const checkRef = useRef<HTMLInputElement[]>([]);

  const [idCheckStatus, setIdCheckStatus] = useState<IdCheckStatus>({
    checked: false,
    available: false,
  });
  const currentPath = location.pathname;

  let breadcrumbText = "사용자 관리";

  if (currentPath.includes('admin/members/create')) {
    breadcrumbText = "사용자 등록";
  } else if (currentPath.includes('admin/members/modify')) {
    breadcrumbText = "사용자 수정";
  }

  const uniqId = location.state?.uniqId || "";
  const mberSttusRadioGroup = [
    { value: "P", label: "가능" },
    { value: "A", label: "대기" },
    { value: "D", label: "탈퇴" },
  ];

  let [groupCodeOptions, setGroupCodeOptions] = useState<Option[]>([]);
  const [modeInfo, setModeInfo] = useState<ModeInfo>({ mode });
  const [memberDetail, setMemberDetail] = useState<MemberDetail>({});
  const [deptCdOptions, setDeptCdOptions] = useState<Option[]>([]);
  const [deptSubCdOptions, setdeptSubCdOptions] = useState<Option[]>([]);

  const initMode = () => {
    switch (mode) {
      case CODE.MODE_CREATE:
        setModeInfo({
          ...modeInfo,
          modeTitle: "등록",
          editURL: "/members/insert",
        });
        break;

      case CODE.MODE_MODIFY:
        setModeInfo({
          ...modeInfo,
          modeTitle: "수정",
          editURL: `/members/update`,
        });
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
    }

    if (modeInfo.mode === CODE.MODE_MODIFY) {
      retrieveDetailURL = `/members/update/${uniqId}`;
    }

    const requestOptions = {
      method: "GET",
      headers: {
        "Content-type": "application/json",
      },
    };

    const fetchSubDept = async (deptCd: string, currentSubCd: string) => {
      try {
        const resp = await axios.get(
          "/geoportal/api/api/deptSubList",
          { params: { deptCd }, withCredentials: true }
        );

        const subOptions = (resp.data.deptSubList_result || []).map(item => ({
          value: item.code,
          label: item.codeNm,
        }));

        setdeptSubCdOptions(subOptions);

        if (currentSubCd && subOptions.some(opt => opt.value === currentSubCd)) {
          setMemberDetail(prev => ({ ...prev, deptSubCd: currentSubCd }));
        } else {
          setMemberDetail(prev => ({ ...prev, deptSubCd: "" }));
        }
      } catch (error) {
        console.error("하위 부서 목록 불러오기 실패", error);
      }
    };

    EgovNet.requestFetch(retrieveDetailURL, requestOptions, (resp) => {
      if (modeInfo.mode === CODE.MODE_MODIFY) {
        const data = resp.result.mberManageVO;
        setMemberDetail(data);

        if (data.deptCd) {
          fetchSubDept(data.deptCd, data.deptSubCd);
        }
      }

      groupCodeOptions = [];
      resp.result.groupId_result.forEach((item) => {
        groupCodeOptions.push({ value: item.code, label: item.codeNm });
      });
      setGroupCodeOptions(groupCodeOptions);

      let deptOptions: Option[] = [];
      resp.result.deptList_result.forEach(item => {
        deptOptions.push({ value: item.code, label: item.codeNm });
      });

      const adminDeptOption: Option = { value: '0000000', label: '관리자' };
      deptOptions.unshift(adminDeptOption);
      setDeptCdOptions(deptOptions);

      let deptSubCdOptions: Option[] = [];
      resp.result.deptSubList_result.forEach(item => {
        deptSubCdOptions.push({ value: item.code, label: item.codeNm });
      });
      setdeptSubCdOptions(deptSubCdOptions);
    });
  };

  const checkIdDplct = (): Promise<number> => {
    return new Promise((resolve) => {
      let checkId = memberDetail["mberId"];
      if (!checkId) {
        alert("사용자 ID를 입력해 주세요");
        setIdCheckStatus({ checked: false, available: false });
        resolve(1);
        return;
      }

      if (checkId.length < 5) {
        alert("아이디는 5글자 이상이어야 합니다.");
        setIdCheckStatus({ checked: false, available: false });
        resolve(-1);
        return;
      }

      const checkIdURL = `/etc/member_checkid/${checkId}`;
      const reqOptions = {
        method: "GET",
        headers: {
          "Content-type": "application/json",
        },
      };

      EgovNet.requestFetch(checkIdURL, reqOptions, (resp) => {
        if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS) && resp.result.usedCnt > 0) {
          setMemberDetail({
            ...memberDetail,
            checkIdResult: "이미 사용중인 아이디입니다. [ID체크]",
          });
          alert("이미 사용중인 아이디입니다.");
          resolve(resp.result.usedCnt);
          setIdCheckStatus({ checked: true, available: false });
        } else {
          setMemberDetail({
            ...memberDetail,
            checkIdResult: "사용 가능한 아이디입니다.",
          });
          alert("사용 가능한 아이디입니다.");
          setIdCheckStatus({ checked: true, available: true });
          resolve(0);
        }
      });
    });
  };

  const formValidator = (formData: FormData): Promise<boolean> => {
    return new Promise((resolve) => {
      if (!formData.get("mberId")) {
        alert("사용자 ID는 필수 값입니다.");
        return resolve(false);
      }

      if (!idCheckStatus.checked) {
        alert("아이디 중복 체크를 해주세요.");
        return resolve(false);
      }

      if (!idCheckStatus.available) {
        return resolve(false);
      }

      const password = formData.get("password");
      if (!password) {
        alert("암호는 필수 값입니다.");
        return resolve(false);
      }

      const reg = /^(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).{8,}$/;
      if (!reg.test(String(password))) {
        alert(
          "비밀번호는 8자 이상이어야 하며, 숫자/영문자/특수문자를 모두 포함해야 합니다."
        );
        checkRef.current[1].value = "";
        return resolve(false);
      }

      if (!formData.get("mberNm")) {
        alert("사용자 명은 필수 값입니다.");
        return resolve(false);
      }

      if (!formData.get("groupId")) {
        alert("권한 그룹은 필수 값입니다.");
        return resolve(false);
      }

      if (!formData.get("mberSttus")) {
        alert("사용자 상태값은 필수 값입니다.");
        return resolve(false);
      }

      if (!formData.get("deptCd")) {
        alert("부서 코드는 필수 값입니다.");
        return resolve(false);
      }

      resolve(true);
    });
  };

  const formObjValidator = (): boolean => {
    if (checkRef.current[0].value === "") {
      alert("사용자 ID는 필수 값입니다.");
      return false;
    }

    if (checkRef.current[1].value === "") {
      memberDetail.password = "";
    } else {
      const password = checkRef.current[1].value;
      const reg = /^(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).{8,}$/;
      if (!reg.test(password)) {
        alert(
          "비밀번호는 8자 이상이어야 하며, 숫자/영문자/특수문자를 모두 포함해야 합니다."
        );
        checkRef.current[1].value = "";
        return false;
      }
      memberDetail.password = password;
    }

    if (checkRef.current[2].value === "") {
      alert("사용자 명은 필수 값입니다.");
      return false;
    }

    return true;
  };

  const updateMember = () => {
    let modeStr = modeInfo.mode === CODE.MODE_CREATE ? "POST" : "PUT";
    let requestOptions = {};

    if (modeStr === "POST") {
      const formData = new FormData();
      if (!memberDetail.deptSubCd || memberDetail.deptSubCd === "") {
        memberDetail.deptCd = memberDetail.deptCd;
      } else {
        memberDetail.deptCd = memberDetail.deptSubCd;
      }

      for (let key in memberDetail) {
        formData.append(key, String(memberDetail[key]));
      }

      formValidator(formData).then((res) => {
        if (res) {
          requestOptions = {
            method: modeStr,
            headers: {},
            body: formData,
          };

          EgovNet.requestFetch(modeInfo.editURL!, requestOptions, (resp) => {
            if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
              alert("사용자 정보가 등록되었습니다.");
              navigate({ pathname: URL.ADMIN_MEMBERS });
            } else {
              navigate(
                { pathname: URL.ERROR },
                { state: { msg: resp.resultMessage } }
              );
            }
          });
        }
      });
    } else {
      if (formObjValidator()) {
        requestOptions = {
          method: modeStr,
          headers: {
            "Content-type": "application/json",
          },
          body: JSON.stringify({ ...memberDetail }),
        };

        EgovNet.requestFetch(modeInfo.editURL!, requestOptions, (resp) => {
          if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
            navigate({ pathname: URL.ADMIN_MEMBERS });
          } else {
            navigate(
              { pathname: URL.ERROR },
              { state: { msg: resp.resultMessage } }
            );
          }
        });
      }
    }
  };

  const deleteMember = (uniqId: string) => {
    const deleteMemberURL = `/members/delete/${uniqId}`;

    const requestOptions = {
      method: "DELETE",
      headers: {
        "Content-type": "application/json",
      },
    };

    EgovNet.requestFetch(deleteMemberURL, requestOptions, (resp) => {
      console.log("====>>> member delete= ", resp);
      if (Number(resp.resultCode) === Number(CODE.RCV_SUCCESS)) {
        alert("사용자가 삭제되었습니다.");
        navigate(URL.ADMIN_MEMBERS, { replace: true });
      } else {
        alert("ERR : " + resp.resultMessage);
      }
    });
  };

  useEffect(() => {
    if (memberDetail.deptCd) {
      const fetchSubDept = async () => {
        const resp = await axios.get(
          "/geoportal/api/api/deptSubList",
          {
            params: { deptCd: memberDetail.deptCd },
            withCredentials: true,
          }
        );
        const deptSubCdOptions = (resp.data.deptSubList_result || []).map(
          (item) => ({
            value: item.code,
            label: item.codeNm,
          })
        );

        setdeptSubCdOptions(deptSubCdOptions);

        if (
          memberDetail.deptSubCd &&
          !deptSubCdOptions.some((opt) => opt.value === memberDetail.deptSubCd)
        ) {
          setMemberDetail((prev) => ({ ...prev, deptSubCd: "" }));
        }
      };
      fetchSubDept();
    }
  }, [memberDetail.deptCd]);

  useEffect(() => {
    initMode();
  }, []);

  console.log("------------------------------EgovAdminMemberEdit [End]");
  console.groupEnd("EgovAdminMemberEdit");

  return (
    <div className="new_wrap2" id="warp2">
      <div className="w100 d_flex d_jcc">
        <div className="w1200">
          <div className="nav_wrap d_flex d_end">
            <div className="nav d_flex d_end">
              <Link to={URL.MAIN}><div className="nav_ico img_all"></div></Link>
              <div className="nav_ico_arr img_all"></div>
              <Link to={URL.ADMIN}><div className="nav_txt">시스템 운영관리</div></Link>
              <div className="nav_ico_arr img_all"></div>
              <Link><div className="nav_txt">{breadcrumbText}</div></Link>
            </div>
          </div>
        </div>
      </div>
      <div className="con_wrap d_flex d_jcc">
        <div className="join">
          <h1 className="txt_cen join_h1">{modeInfo.mode === CODE.MODE_CREATE ? '사용자 등록' : '사용자 수정'}</h1>
          <div className="join_txt_s">본 작성항목은 모두 필수 항목입니다.</div>
          <div className="blue_line"></div>

          <div className="join_box d_flex aic">
            <label htmlFor="user_id">사용자 ID<span>*</span></label>
            {modeInfo.mode === CODE.MODE_CREATE ? (
              <>
                <input type="text"
                  id="user_id"
                  className="join_ser1"
                  name="mberId"
                  placeholder="사용자 ID는 5글자 이상 입력 해 주세요."
                  defaultValue={memberDetail.mberId}
                  onChange={(e) =>
                    setMemberDetail({
                      ...memberDetail,
                      mberId: e.target.value,
                    })
                  }
                />
                <div className="grey_btn" onClick={() => {
                  checkIdDplct();
                }}>중복 ID 체크</div>
              </>
            ) : (
              <>
                <input type="text"
                  id="user_id"
                  className="join_ser2"
                  name="mberId"
                  readOnly
                  defaultValue={memberDetail.mberId}
                  ref={(el) => (checkRef.current[0] = el)}
                  required
                />
              </>
            )}
          </div>

          <div className="join_box d_flex aic">
            <label htmlFor="user_pass">사용자 패스워드<span>*</span></label>
            {modeInfo.mode === CODE.MODE_CREATE ? (
              <>
                <input type="password" id="user_pass" name="password"
                  className="join_ser2"
                  placeholder="8자리 이상 영문, 숫자, 특수문자를 포함해 주세요."
                  defaultValue={memberDetail.password}
                  onChange={(e) =>
                    setMemberDetail({
                      ...memberDetail,
                      password: e.target.value,
                    })
                  }
                  ref={(el) => (checkRef.current[1] = el)}
                  required
                />
              </>
            ) : (
              <>
                <input type="password" id="user_pass" className="join_ser2" name="password"
                  onChange={(e) =>
                    setMemberDetail({
                      ...memberDetail,
                      password: e.target.value,
                    })
                  }
                  ref={(el) => (checkRef.current[1] = el)}
                  placeholder="8자리이상 영문, 숫자, 특수문자를 포함 해 주세요."
                />
              </>
            )}
          </div>

          <div className="join_box d_flex aic">
            <label htmlFor="user_name2">사용자 명<span>*</span></label>
            <input type="text" id="user_name2" name="mberNm" className="join_ser2"
              defaultValue={memberDetail.mberNm}
              onChange={(e) =>
                setMemberDetail({
                  ...memberDetail,
                  mberNm: e.target.value,
                })
              }
              ref={(el) => (checkRef.current[2] = el)}
              required />
          </div>

          <div className="join_box d_flex aic">
            <label htmlFor="groupId">사용자 권한<span>*</span></label>
            <select id="groupId" name="groupId" title="회원권한유형선택"
              className="join_ser3"
              onChange={(e) =>
                setMemberDetail({
                  ...memberDetail,
                  groupId: e.target.value,
                })
              }
              value={memberDetail.groupId}>
              {groupCodeOptions.map((option) => {
                return (
                  <option value={option.value} key={option.value}>
                    {option.label}
                  </option>
                );
              })}
            </select>
          </div>

          <div className="join_box d_flex aic">
            <label htmlFor="deptCd">소속 부서<span>*</span></label>
            <select id="deptCd" name="deptCd" title="소속 부서 선택" className="join_ser4"
              onChange={async (e) => {
                const selectedDept = e.target.value;

                setMemberDetail({
                  ...memberDetail, deptCd: