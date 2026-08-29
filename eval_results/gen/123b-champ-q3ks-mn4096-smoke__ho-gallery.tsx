import React from "react";
import { SERVER } from "@/config";

interface EgovImageGalleryProps {
  boardFiles?: Array<{ atchFileId: string; fileSn: number }>;
}

function EgovImageGallery({ boardFiles }: EgovImageGalleryProps) {
  let filesTag: JSX.Element[] = [];

  if (boardFiles !== undefined) {
    boardFiles.forEach((item, index) => {
      filesTag.push(
        React.createElement("img", {
          key: index,
          src: `${SERVER}/image?atchFileId=${item.atchFileId}&amp; fileSn=${item.atchFileId}`,
          alt: "",
        })
      );
    });
  }
  console.log("filesTag : ", filesTag);
  console.groupEnd("EgovAttachFile");

  return React.createElement("div", { className: "board-attach-img" }, filesTag);
}

export default EgovImageGallery;