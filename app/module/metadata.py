import os

from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint, TIMESTAMP, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

Base = declarative_base()


class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    filename = Column(String, default="/")
    path = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    owner = Column(Integer, nullable=False)
    file_group = Column(String, nullable=False)
    is_directory = Column(Boolean, nullable=False)
    permissions = Column(Integer, default=740)
    upload_date = Column(TIMESTAMP, default=func.now())

    __table_args__ = (
        UniqueConstraint('filename', 'path', 'owner', name='_filename_path_owner_uc'),
    )


class UserMetadata:
    def __init__(self, db_path):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def _sanitize_path(self, path):
        if not path:
            return '/'
        norm = os.path.normpath('/' + str(path).lstrip('/'))
        return '/' if norm == '.' else norm

    def add_file(self, filename, owner, file_group, size, is_directory=False, permissions=740, path='/'):
        sanitized_path = self._sanitize_path(path)
        session = self.Session()

        new_file = File(
            filename=filename,
            path=sanitized_path,
            owner=owner,
            file_group=file_group,
            size=size,
            is_directory=is_directory,
            permissions=permissions
        )

        try:
            session.add(new_file)
            session.commit()
        except IntegrityError:
            session.rollback()
        finally:
            session.close()

    def remove_file(self, filename):
        session = self.Session()

        try:
            file_to_remove = session.query(File).filter(File.filename == filename).first()
            if file_to_remove:
                session.delete(file_to_remove)
                session.commit()
        finally:
            session.close()

    def rename_file(self, new_name, new_path, file_id):
        sanitized_path = self._sanitize_path(new_path)
        session = self.Session()

        try:
            file_to_rename = session.query(File).filter(File.id == file_id).first()
            if file_to_rename:
                file_to_rename.filename = new_name
                file_to_rename.path = sanitized_path
                session.commit()
        finally:
            session.close()

    def get_files(self, path):
        sanitized_path = self._sanitize_path(path)
        session = self.Session()

        try:
            files = session.query(File).filter(File.path == sanitized_path).order_by(File.upload_date.desc()).all()
            return [{
                'id': file.id,
                'name': file.filename,
                'owner': file.owner,
                'group': file.file_group,
                'size': file.size,
                'is_directory': file.is_directory,
                'permissions': file.permissions
            } for file in files]
        finally:
            session.close()

    def list_subdirectories(self, path):
        path = self._sanitize_path(path).rstrip('/')
        like = f"{path}/%" if path else "/%"
        session = self.Session()

        try:
            rows = session.query(File.path).filter(File.path.like(like)).distinct().all()
            children = set()
            for (p,) in rows:
                if not p.startswith('/'):
                    p = '/' + p.lstrip('/')
                if p == path or p == (path or '/'):
                    continue
                rel = p[len(path):].lstrip('/') if path else p.lstrip('/')
                if not rel:
                    continue
                first = rel.split('/', 1)[0]
                full = (path + '/' + first) if path else '/' + first
                children.add(full)

            return sorted([(os.path.basename(d), d) for d in children], key=lambda x: x[0].lower())
        finally:
            session.close()

    def get_file_path_by_id(self, file_id):
        session = self.Session()

        try:
            file_data = session.query(File.filename, File.path).filter(File.id == file_id).first()
            return file_data
        finally:
            session.close()

