import React from "react";
import { SERVER_URL } from "@/config";

interface IEgovImageGalleryProps {
  boardFiles: Array<{ atchFileId: string; fileSn: string }>;
}

const EgovImageGallery: React.FC<IEgovImageGalleryProps > = ({ boardFiles }) => {
  const filesTag: JSX.Element[] = [];

  if (boardFiles !== undefined) {
    boardFiles.forEach((item, index) => {
      filesTag.push(
        <React.Fragment key={index}>
          <img
            src={`${SERVER_URL}/image?atchFileId=${item.atchFileId}& fileSn=${item.fileSn}`}
            alt=""
          />
          <br />
        </React.Fragment>
      );
    });
  }

  console.log("filesTag : ", filesTag);
  console.groupEnd("EgovAttachFile");

  return <div className="board_attach_img">{filesTag}</div>;
};

export default EgovImageGallery;