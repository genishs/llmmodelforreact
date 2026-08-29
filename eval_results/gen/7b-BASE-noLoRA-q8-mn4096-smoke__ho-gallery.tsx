import React from "react";
import { SERVER_URL } from "@/config";

interface EgovImageGalleryProps {
  boardFiles: { atchFileId: string; fileSn: number }[];
}

function EgovImageGallery({ boardFiles }: EgovImageGalleryProps) {
  let filesTag: JSX.Element[] = [];

  if (boardFiles !== undefined) {
    boardFiles.forEach(function (item, index) {
      filesTag.push(
        <React.Fragment key={index}>
          <img
            src={`${SERVER_URL}/image?atchFileId=${item.atchFileId}&amp;${item.fileSn}`}
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
}

export default EgovImageGallery;